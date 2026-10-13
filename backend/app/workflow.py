import sqlite3
from sqlalchemy import select, update
from typing import TypedDict
from uuid import uuid4
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command
from .db import Session, Incident, Asset, WorkOrder, Crew, log, now
from .services import crew_candidates
from .llm import router, Diagnosis, Plan


class State(TypedDict):
    incident_id: str
    diagnosis: dict
    work_order_id: str
    decision: str


def diagnose(state):
    iid = state['incident_id']
    with Session() as s:
        inc = s.get(Incident, iid)
        snap = inc.snapshot
    p = snap.get('prediction') or {}
    label = p.get('classification', 'review')
    if not snap['monitor']['connected']:
        label = 'review'
    observations = [f'{key}: latest {v["latest"]:.4f}, observed range {v["min"]:.4f}–{v["max"]:.4f}.'
                    for key, v in snap['channels'].items() if key.startswith(('Pressure', 'Water Flow'))][:4]
    fallback = {'classification': label, 'priority': 'high' if label == 'leak' else 'medium',
        'summary': ('No trained Monitor is connected. This review summarises the recorded sensor window; the cause remains unclassified.'
                    if label == 'review' else f'The Monitor proposes {label.replace("_", " ")}. Verify the sensor evidence before authorising an inspection.'),
        'evidence': observations or ['No sensor observations are available.'],
        'recommended_action': 'Verify meter readings and instrument operation. Inspect the water system if abnormal readings persist.'}
    log('Diagnosis', 'Retrieved sensor history and channel statistics. Assessing the evidence.', iid)
    result, provider, failures = router.structured('Assess this recorded sensor window and propose an inspection. Respect the Monitor availability.', snap, Diagnosis, fallback)
    if not snap['monitor']['connected']:
        result['classification'] = 'review'
        result['priority'] = 'medium'
    # Numerical observations are always retained separately from LLM-generated text.
    result.update({'provider': provider, 'observations': observations, 'provider_attempts': failures})
    with Session.begin() as s:
        inc = s.get(Incident, iid)
        inc.diagnosis = result
        inc.classification = result['classification']
        inc.priority = result['priority']
    log('Diagnosis', 'Evidence review complete. ' + ('Evidence-only mode; no LLM response was available.' if provider == 'evidence_only' else 'Structured LLM output validated.'), iid, provider)
    return {'diagnosis': result}


def dispatch(state):
    iid = state['incident_id']
    diagnosis = state['diagnosis']
    with Session() as s:
        existing = s.scalar(select(WorkOrder).where(WorkOrder.incident_id == iid))
        if existing:
            return {'work_order_id': existing.id}
        inc = s.get(Incident, iid)
        asset = s.get(Asset, inc.asset_id)
        asset_id, zone, name = asset.id, asset.zone, asset.name
    candidates = crew_candidates(diagnosis['classification'], zone)
    fallback = {'title': f'Inspect readings at {name}', 'instructions': diagnosis['recommended_action'],
                'crew_id': candidates[0]['id'] if candidates else None}
    log('Dispatch', f'Checked {len(candidates)} eligible configured crews. Preparing a draft task.', iid)
    plan, provider, _ = router.structured('Prepare an inspection task. Pick only an eligible crew ID, or null. Do not claim dispatch has occurred.',
                                        {'diagnosis': diagnosis, 'eligible_crews': candidates}, Plan, fallback)
    if plan['crew_id'] not in {c['id'] for c in candidates}:
        plan['crew_id'] = fallback['crew_id']
    with Session.begin() as s:
        order = WorkOrder(id='WO-' + uuid4().hex[:8].upper(), incident_id=iid, asset_id=asset_id,
            title=plan['title'], instructions=plan['instructions'], priority=diagnosis['priority'], crew_id=plan['crew_id'])
        s.add(order)
        s.get(Incident, iid).status = 'pending_approval'
        wid = order.id
    log('Orchestrator', 'Draft work order is awaiting human approval. No crew has been dispatched.', iid, provider)
    return {'work_order_id': wid}


def approval(state):
    response = interrupt({'work_order_id': state['work_order_id'], 'incident_id': state['incident_id'], 'action': 'approve_or_reject'})
    decision = response['decision']
    with Session.begin() as s:
        order = s.get(WorkOrder, state['work_order_id'])
        if order.status != 'pending_approval':
            raise ValueError('This work order already has a decision.')
        if decision == 'approve':
            crew = s.get(Crew, order.crew_id) if order.crew_id else None
            asset = s.get(Asset, order.asset_id)
            required_skill = 'instrumentation' if s.get(Incident, state['incident_id']).classification == 'sensor_fault' else 'water'
            if not crew or not crew.available or crew.skill != required_skill or crew.zone not in ['all', asset.zone]:
                raise ValueError('The proposed crew is no longer eligible or available.')
            reserved = s.execute(update(Crew).where(Crew.id == crew.id, Crew.available == True).values(available=False))
            if reserved.rowcount != 1:
                raise ValueError('The proposed crew is no longer available.')
            order.status = 'approved'
            order.approved_at = now()
            s.get(Incident, state['incident_id']).status = 'approved'
        else:
            order.status = 'rejected'
            s.get(Incident, state['incident_id']).status = 'rejected'
        order.decision_note = response.get('note')
    log('Human approval', f'Work order {"approved" if decision == "approve" else "rejected"} by the operator.', state['incident_id'])
    return {'decision': decision}


class Workflow:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        builder = StateGraph(State)
        builder.add_node('diagnosis', diagnose)
        builder.add_node('dispatch', dispatch)
        builder.add_node('approval', approval)
        builder.add_edge(START, 'diagnosis')
        builder.add_edge('diagnosis', 'dispatch')
        builder.add_edge('dispatch', 'approval')
        builder.add_edge('approval', END)
        self.graph = builder.compile(checkpointer=SqliteSaver(self.conn))

    def run(self, incident_id):
        try:
            self.graph.invoke({'incident_id': incident_id}, {'configurable': {'thread_id': incident_id}})
        except Exception as e:
            with Session.begin() as s:
                inc = s.get(Incident, incident_id)
                inc.status = 'error'
                inc.error = f'Workflow could not complete: {type(e).__name__}'
            log('Orchestrator', 'Investigation needs attention. Check the backend logs or retry the incident.', incident_id)
            raise

    def resume(self, incident_id, decision, note):
        # Reject an invalid approval before LangGraph persists the resume value.
        # The node rechecks eligibility when it reserves the crew.
        with Session() as s:
            order = s.scalar(select(WorkOrder).where(WorkOrder.incident_id == incident_id))
            if not order or order.status != 'pending_approval':
                raise ValueError('This work order is not awaiting a decision.')
            if decision == 'approve':
                crew = s.get(Crew, order.crew_id) if order.crew_id else None
                asset = s.get(Asset, order.asset_id)
                required_skill = 'instrumentation' if s.get(Incident, incident_id).classification == 'sensor_fault' else 'water'
                if not crew or not crew.available or crew.skill != required_skill or crew.zone not in ['all', asset.zone]:
                    raise ValueError('The proposed crew is no longer eligible or available.')
        self.graph.invoke(Command(resume={'decision': decision, 'note': note}), {'configurable': {'thread_id': incident_id}})

    def close(self):
        self.conn.close()

