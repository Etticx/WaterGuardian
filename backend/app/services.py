from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .db import Asset, Reading, Incident, Crew, WorkOrder, Activity, Session, Base, engine, serialize, log
from .dataset import Dataset
from .monitor import monitor

dataset = Dataset()


def bootstrap():
    Base.metadata.create_all(engine)
    runs = dataset.default_runs()
    with Session.begin() as s:
        if not s.scalar(select(Asset.id).limit(1)):
            for i, (zone, name) in enumerate([('industrial', 'Industrial facilities'), ('parks', 'Parks and irrigation'), ('malls', 'Malls')]):
                a = Asset(id=f'zone-{i+1}', name=name, zone=zone, recording_id=runs[i], cursor=120, session_id=str(uuid4()))
                s.add(a)
                s.flush()
                for j, values in enumerate(dataset.read(runs[i])[:120]):
                    s.add(Reading(asset_id=a.id, session_id=a.session_id, sample_index=j, values=values))
            s.add_all([
                Crew(id='crew-water', name='Water maintenance team', skill='water', zone='all'),
                Crew(id='crew-meter', name='Meter and instrumentation team', skill='instrumentation', zone='all'),
                Crew(id='crew-landscape', name='Landscape maintenance team', skill='water', zone='parks'),
            ])
            s.add(Activity(agent='System', message='Loaded real recorded measurements into three illustrative zones. ML training is separate.'))


def asset_snapshot(asset_id):
    with Session() as s:
        a = s.get(Asset, asset_id)
        if not a:
            raise KeyError('Asset not found')
        rows = list(s.scalars(select(Reading).where(Reading.asset_id == asset_id, Reading.session_id == a.session_id).order_by(Reading.id.desc()).limit(180)))[::-1]
        return {**serialize(a), 'total_samples': len(dataset.read(a.recording_id)),
                'latest': serialize(rows[-1]) if rows else None,
                'history': [{'sample_index': r.sample_index, **r.values} for r in rows],
                'readings_count': s.scalar(select(func.count(Reading.id)).where(Reading.asset_id == asset_id, Reading.session_id == a.session_id))}


def evidence_snapshot(asset_id):
    snap = asset_snapshot(asset_id)
    rows = snap['history'][-60:]
    summary = {}
    if rows:
        for channel in rows[-1]:
            if channel == 'sample_index':
                continue
            vals = [r[channel] for r in rows if channel in r]
            summary[channel] = {'latest': vals[-1], 'min': min(vals), 'max': max(vals), 'mean': round(sum(vals)/len(vals), 6)}
    # No recording filename, recording category, ground truth, or target column is exposed.
    return {'asset_id': asset_id, 'sample_count': len(rows), 'start_sample': rows[0]['sample_index'] if rows else None,
            'end_sample': rows[-1]['sample_index'] if rows else None, 'channels': summary,
            'prediction': snap['latest']['prediction'] if snap['latest'] else None,
            'monitor': {'connected': monitor.status()['connected'], 'version': monitor.status()['version']},
            'units': 'Original sensor units; calibration and original sampling interval not configured.'}


def create_incident(asset_id, origin='manual'):
    snapshot = evidence_snapshot(asset_id)
    if not snapshot['sample_count']:
        raise ValueError('Replay some readings before requesting an investigation.')
    active = select(Incident).where(Incident.asset_id == asset_id, Incident.status.in_(['investigating', 'pending_approval', 'approved', 'in_progress']))
    try:
        with Session.begin() as s:
            existing = s.scalar(active)
            if existing:
                return serialize(existing), False
            asset = s.get(Asset, asset_id)
            incident = Incident(id='INC-' + uuid4().hex[:8].upper(), asset_id=asset_id,
                title=f'Reading review · {asset.name}', snapshot=snapshot)
            s.add(incident)
            s.flush()
            result = serialize(incident)
    except IntegrityError:
        with Session() as s:
            existing = s.scalar(active)
            if not existing:
                raise
            return serialize(existing), False
    log('Orchestrator', f'Investigation opened from {origin} review.', result['id'])
    return result, True


def crew_candidates(classification, zone):
    skill = 'instrumentation' if classification == 'sensor_fault' else 'water'
    with Session() as s:
        return [serialize(c) for c in s.scalars(select(Crew).where(Crew.available == True, Crew.skill == skill, Crew.zone.in_(['all', zone])))]


def overview():
    with Session() as s:
        assets = [asset_snapshot(a.id) for a in s.scalars(select(Asset).order_by(Asset.id))]
        incidents = [serialize(i) for i in s.scalars(select(Incident).order_by(Incident.created_at.desc()))]
        orders = [serialize(w) for w in s.scalars(select(WorkOrder).order_by(WorkOrder.created_at.desc()))]
        crews = [serialize(c) for c in s.scalars(select(Crew))]
        activities = [serialize(a) for a in s.scalars(select(Activity).order_by(Activity.id.desc()).limit(80))]
    return {'assets': assets, 'incidents': incidents, 'work_orders': orders, 'crews': crews, 'activity': activities,
            'monitor': monitor.status(), 'provenance': 'WDSEventDB physical laboratory measurements · illustrative zone assignments',
            'stats': {'zones': len(assets), 'readings': sum(a['readings_count'] for a in assets),
                      'open_incidents': sum(i['status'] not in ['completed', 'rejected'] for i in incidents),
                      'pending_approval': sum(w['status'] == 'pending_approval' for w in orders)}}

