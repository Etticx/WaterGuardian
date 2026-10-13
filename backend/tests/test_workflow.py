from sqlalchemy import select, func
from backend.app import main
from backend.app.db import Session, Incident, Reading, Crew
from backend.app.workflow import Workflow
from backend.app.config import settings


def investigate(client, asset='zone-1'):
    response = client.post(f'/api/assets/{asset}/investigate')
    assert response.status_code == 200
    result = client.get('/api/overview').json()
    return result['work_orders'][-1], response.json()['incident']


def test_real_readings_no_labels_or_fabricated_predictions(client):
    data = client.get('/api/overview').json()
    assert data['stats']['readings'] == 360
    assert data['monitor']['connected'] is False
    for asset in data['assets']:
        row = main.dataset.read(asset['recording_id'])[119]
        assert asset['latest']['values'] == row
        assert 'Labels' not in row
        assert asset['latest']['prediction'] is None
        assert asset['status'] == 'model_pending'
    assert client.get('/api/evaluation').json()['available'] is False


def test_telemetry_preserves_values_and_rejects_ground_truth(client):
    a = client.get('/api/overview').json()['assets'][0]
    values = main.dataset.read(a['recording_id'])[120]
    packet = dict(device_id=a['id'], session_id=a['session_id'], sample_index=120, readings=values)
    assert client.post('/api/telemetry', json=packet).json()['prediction'] is None
    assert client.post('/api/telemetry', json=packet).json()['duplicate'] is True
    with Session() as s:
        assert s.scalar(select(func.count(Reading.id))) == 361
    assert client.get('/api/overview').json()['assets'][0]['latest']['values'] == values
    assert client.post('/api/telemetry', json={**packet, 'readings': {**values, 'Labels': 1}}).status_code == 422
    assert client.post('/api/telemetry', json={**packet, 'target': 1}).status_code == 422
    assert client.post('/api/telemetry', json={**packet, 'session_id': 'old-session'}).status_code == 409


def test_recording_selection_and_empty_review(client):
    a = client.get('/api/overview').json()['assets'][0]
    r = client.post('/api/replay/configure', json={'asset_id': a['id'], 'recording_id': a['recording_id'], 'start_sample': 0})
    assert r.status_code == 200
    assert client.post('/api/assets/zone-1/investigate').status_code == 422
    with Session() as s:
        assert s.scalar(select(func.count(Incident.id))) == 0
    assert client.post('/api/replay/control/pause?interval=0').status_code == 422
    assert client.post('/api/replay/control/reset').status_code == 200


def test_approval_persists_across_workflow_restart_and_required_before_work(client):
    order, inc = investigate(client)
    assert order['status'] == 'pending_approval'
    assert client.patch(f"/api/work-orders/{order['id']}/status?status=in_progress").status_code == 409
    repeated = client.post('/api/assets/zone-1/investigate').json()
    assert repeated['created'] is False
    assert repeated['incident']['id'] == inc['id']
    data = client.get('/api/overview').json()
    assert len(data['work_orders']) == 1
    diagnosis = data['incidents'][0]['diagnosis']
    assert data['incidents'][0]['classification'] == 'review'
    assert diagnosis['provider'] == 'evidence_only'
    assert 'Labels' not in str(data['incidents'][0]['snapshot'])
    assert 'LeakEvent' not in str(data['incidents'][0]['snapshot'])
    assert all(c['available'] for c in data['crews'])
    main.workflow.close()
    main.workflow = Workflow(settings.path(settings.workflow_database_path))
    endpoint = f"/api/work-orders/{order['id']}"
    assert client.post(endpoint + '/decision', json={'decision': 'approve', 'note': 'Inspect instruments first'}).status_code == 200
    assert client.post(endpoint + '/decision', json={'decision': 'approve'}).status_code == 409
    with Session() as s:
        assert not s.get(Crew, order['crew_id']).available
    assert client.patch(endpoint + '/status?status=completed').status_code == 409
    assert client.patch(endpoint + '/status?status=in_progress').status_code == 200
    assert client.patch(endpoint + '/status?status=completed').status_code == 200
    with Session() as s:
        assert s.get(Crew, order['crew_id']).available


def test_crew_is_rechecked_at_approval_and_rejection_remains_possible(client):
    order, _ = investigate(client)
    with Session.begin() as s:
        s.get(Crew, order['crew_id']).available = False
    endpoint = f"/api/work-orders/{order['id']}/decision"
    assert client.post(endpoint, json={'decision': 'approve'}).status_code == 409
    assert client.post(endpoint, json={'decision': 'reject', 'note': 'Crew unavailable'}).status_code == 200
    assert client.get('/api/overview').json()['work_orders'][0]['status'] == 'rejected'


def test_future_monitor_prediction_opens_one_investigation(client):
    # An inference stub verifies the integration; no estimator is trained here.
    class ConnectedModelStub:
        def predict(self, x):
            return [1]
    main.monitor.bundle = {'model': ConnectedModelStub(), 'features': ['Water Flow 1'],
        'class_map': {'1': 'leak'}, 'version': 'adapter-test'}
    a = client.get('/api/overview').json()['assets'][0]
    for index in [120, 121]:
        response = client.post('/api/telemetry', json={'device_id': a['id'], 'session_id': a['session_id'],
            'sample_index': index, 'readings': main.dataset.read(a['recording_id'])[index]})
        assert response.status_code == 200
        assert response.json()['prediction']['classification'] == 'leak'
    result = client.get('/api/overview').json()
    assert len(result['incidents']) == len(result['work_orders']) == 1
    assert result['incidents'][0]['classification'] == 'leak'
    assert result['work_orders'][0]['status'] == 'pending_approval'
