import asyncio
import json
import math
from contextlib import asynccontextmanager
from uuid import uuid4
from typing import Literal
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import httpx
from .config import settings
from .db import Session, Asset, Reading, Incident, WorkOrder, Crew, log, serialize
from .services import bootstrap, dataset, overview, create_incident
from .monitor import monitor
from .workflow import Workflow


class Telemetry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    device_id: str
    session_id: str
    sample_index: int = Field(ge=0)
    readings: dict[str, float]


class ReplayConfig(BaseModel):
    asset_id: str
    recording_id: str
    start_sample: int = Field(default=0, ge=0)


class Decision(BaseModel):
    decision: Literal['approve', 'reject']
    note: str = Field(default='', max_length=1000)


class Replay:
    def __init__(self):
        self.running = False
        self.interval = 0.5
        self.error = None

    async def publish(self):
        while True:
            if self.running:
                try:
                    with Session() as s:
                        assets = [serialize(a) for a in s.scalars(select(Asset))]
                    packets = []
                    for a in assets:
                        rows = dataset.read(a['recording_id'])
                        if a['cursor'] < len(rows):
                            packets.append({'device_id': a['id'], 'session_id': a['session_id'], 'sample_index': a['cursor'], 'readings': rows[a['cursor']]})
                    if not packets:
                        self.running = False
                        log('Replay', 'All current recordings have reached their final sample.')
                    else:
                        async with httpx.AsyncClient(timeout=10) as c:
                            for packet in packets:
                                r = await c.post(f'http://127.0.0.1:{settings.backend_port}/api/telemetry', json=packet)
                                r.raise_for_status()
                        self.error = None
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.error = f'Telemetry publishing failed: {type(e).__name__}'
                    self.running = False
                    log('Replay', self.error)
            await asyncio.sleep(self.interval)

    def status(self):
        return {'running': self.running, 'interval': self.interval, 'error': self.error}


replay = Replay()
workflow = None
decision_locks = {}


@asynccontextmanager
async def lifespan(app):
    global workflow
    bootstrap()
    workflow = Workflow(settings.path(settings.workflow_database_path))
    task = asyncio.create_task(replay.publish())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        workflow.close()


app = FastAPI(title='Township Water Guardian', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Content-Type'])


@app.get('/api/health')
def health():
    return {'status': 'ok', 'monitor': monitor.status()}


@app.get('/api/overview')
def get_overview():
    return {**overview(), 'replay': replay.status()}


@app.get('/api/recordings')
def recordings():
    return dataset.catalog()


@app.get('/api/settings')
def get_settings():
    # These are statuses, not credentials. Keys never leave the backend.
    return {'providers': [
        {'name': 'Groq', 'model': settings.groq_model, 'configured': bool(settings.groq_api_key)},
        {'name': 'Gemini', 'model': settings.gemini_model, 'configured': bool(settings.gemini_api_key)},
        {'name': 'Ollama', 'model': settings.ollama_model, 'configured': True},
        ], 'monitor': monitor.status(), 'dataset_recordings': len(dataset.paths), 'database': 'SQLite',
        'mode': 'Recorded laboratory replay', 'units': 'Original sensor units', 'crew_mode': 'Configured demonstration roster'}


@app.get('/api/evaluation')
def evaluation():
    path = settings.path(settings.ml_evaluation_path)
    if not path.exists():
        return {'available': False, 'reason': 'Train and evaluate the Monitor separately, then export evaluation.json.'}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not all(k in data for k in ['model_version', 'split_description', 'samples', 'accuracy', 'macro_f1', 'class_names', 'confusion_matrix']):
            raise ValueError('Required evaluation fields are missing')
        n = len(data['class_names'])
        cm = data['confusion_matrix']
        if not n or len(cm) != n or any(len(row) != n for row in cm):
            raise ValueError('Confusion matrix dimensions do not match class_names')
        if any(not isinstance(v, int) or v < 0 for row in cm for v in row) or sum(sum(row) for row in cm) != data['samples']:
            raise ValueError('Confusion matrix counts do not match samples')
        if not (0 <= data['accuracy'] <= 1 and 0 <= data['macro_f1'] <= 1):
            raise ValueError('Metrics must be between 0 and 1')
        return {'available': True, **data}
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(422, detail=f'Invalid evaluation file: {e}')


@app.post('/api/model/reload')
def reload_model():
    status = monitor.reload()
    log('Monitor', 'Model loaded.' if status['connected'] else 'Model not connected. Export a valid joblib bundle to enable predictions.')
    return status


@app.post('/api/telemetry')
async def ingest(packet: Telemetry, tasks: BackgroundTasks):
    if not packet.readings or any(k.lower() in {'labels', 'label', 'target', 'class'} for k in packet.readings):
        raise HTTPException(422, detail='Send sensor channels only; ground truth is prohibited.')
    if any(not math.isfinite(v) for v in packet.readings.values()):
        raise HTTPException(422, detail='Sensor values must be finite.')
    prediction = monitor.predict(packet.readings)
    try:
        with Session.begin() as s:
            a = s.get(Asset, packet.device_id)
            if not a:
                raise HTTPException(404, detail='Unknown device')
            if a.session_id != packet.session_id:
                raise HTTPException(409, detail='Stale replay session')
            if set(packet.readings) != set(dataset.read(a.recording_id)[0]):
                raise HTTPException(422, detail='Sensor channels do not match the configured recording.')
            exists = s.scalar(select(Reading.id).where(Reading.asset_id == a.id, Reading.session_id == a.session_id, Reading.sample_index == packet.sample_index))
            if exists:
                return {'accepted': True, 'duplicate': True}
            s.add(Reading(asset_id=a.id, session_id=a.session_id, sample_index=packet.sample_index, values=packet.readings, prediction=prediction))
            a.cursor = max(a.cursor, packet.sample_index+1)
            a.status = prediction['classification'] if prediction else 'model_pending'
    except IntegrityError:
        # The unique constraint also handles concurrent retransmissions.
        with Session() as s:
            exists = s.scalar(select(Reading.id).where(Reading.asset_id == packet.device_id, Reading.session_id == packet.session_id, Reading.sample_index == packet.sample_index))
        if exists:
            return {'accepted': True, 'duplicate': True}
        raise
    if prediction and prediction['classification'] in ['leak', 'sensor_fault']:
        inc, created = create_incident(packet.device_id, 'Monitor')
        if created:
            tasks.add_task(workflow.run, inc['id'])
    return {'accepted': True, 'prediction': prediction}


@app.post('/api/replay/control/{action}')
def replay_action(action: Literal['start', 'pause', 'reset'], interval: float = 0.5):
    if not 0.1 <= interval <= 5:
        raise HTTPException(422, detail='Playback interval must be between 0.1 and 5 seconds.')
    replay.interval = interval
    replay.running = action == 'start'
    replay.error = None
    if action == 'reset':
        with Session.begin() as s:
            for a in s.scalars(select(Asset)):
                a.session_id = str(uuid4())
                a.cursor = 0
                a.status = 'model_pending' if not monitor.status()['connected'] else 'review'
    log('Replay', {'start': 'Virtual devices started publishing recorded measurements.', 'pause': 'Replay paused.', 'reset': 'New replay sessions created; previous incident evidence is preserved.'}[action])
    return replay.status()


@app.post('/api/replay/configure')
def configure_replay(config: ReplayConfig):
    if replay.running:
        raise HTTPException(409, detail='Pause replay before changing a recording.')
    if config.recording_id not in dataset.paths:
        raise HTTPException(404, detail='Unknown recording')
    rows = dataset.read(config.recording_id)
    if config.start_sample >= len(rows):
        raise HTTPException(422, detail='Sample index is outside this recording.')
    with Session.begin() as s:
        a = s.get(Asset, config.asset_id)
        if not a:
            raise HTTPException(404, detail='Asset not found')
        a.recording_id = config.recording_id
        a.session_id = str(uuid4())
        a.status = 'model_pending' if not monitor.status()['connected'] else 'review'
        # Preload only existing observations up to the selected starting sample.
        a.cursor = config.start_sample
        for j in range(max(0, config.start_sample-180), config.start_sample):
            s.add(Reading(asset_id=a.id, session_id=a.session_id, sample_index=j, values=rows[j]))
    log('Replay', 'Recording assignment updated for ' + config.asset_id)
    return {'configured': True}


@app.post('/api/assets/{asset_id}/investigate')
def investigate(asset_id: str, tasks: BackgroundTasks):
    try:
        inc, created = create_incident(asset_id)
    except KeyError:
        raise HTTPException(404, detail='Asset not found')
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    if created:
        tasks.add_task(workflow.run, inc['id'])
    return {'incident': inc, 'created': created}


@app.post('/api/work-orders/{order_id}/decision')
async def decide(order_id: str, decision: Decision):
    # Serialise approvals across orders because they share the crew roster.
    lock = decision_locks.setdefault('crew_decisions', asyncio.Lock())
    async with lock:
        with Session() as s:
            order = s.get(WorkOrder, order_id)
            if not order:
                raise HTTPException(404, detail='Work order not found')
            if order.status != 'pending_approval':
                raise HTTPException(409, detail='This work order already has a decision.')
            iid = order.incident_id
        try:
            await asyncio.to_thread(workflow.resume, iid, decision.decision, decision.note)
        except ValueError as e:
            raise HTTPException(409, detail=str(e))
    return {'status': 'approved' if decision.decision == 'approve' else 'rejected'}


@app.patch('/api/work-orders/{order_id}/status')
def update_order(order_id: str, status: Literal['in_progress', 'completed']):
    with Session.begin() as s:
        order = s.get(WorkOrder, order_id)
        if not order:
            raise HTTPException(404, detail='Work order not found')
        allowed = {'approved': ['in_progress'], 'in_progress': ['completed']}
        if status not in allowed.get(order.status, []):
            raise HTTPException(409, detail='Approve the task before starting it; start it before completing it.')
        order.status = status
        s.get(Incident, order.incident_id).status = status
        if status == 'completed' and order.crew_id:
            s.get(Crew, order.crew_id).available = True
    log('Work orders', 'Operator marked the demonstration task ' + status.replace('_', ' ') + '.', order.incident_id)
    return {'status': status}

