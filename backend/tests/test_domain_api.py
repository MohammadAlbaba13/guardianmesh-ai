"""Exercise the browser contract through REST, live snapshots and persisted reports."""
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models import Incident
from app.persistence import Repository


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'domain-api.db'}")) as value:
        yield value


def test_domain_contract_catalog_and_wrong_pair_rejected(client):
    domains = client.get("/api/v1/domains").json()
    assert len(domains) == 7
    assert len({d['id'] for d in domains}) == 7
    capabilities = {c['id'] for c in client.get('/api/v1/capabilities').json()}
    for domain in domains:
        response = client.get(f"/api/v1/domains/{domain['id']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail['topology']['service_roots']
        assert detail['scenarios'] == client.get(f"/api/v1/domains/{domain['id']}/scenarios").json()
        assert detail['provider']['mode'] == 'SIMULATED'
        assert detail['reasoner']['mode'] == 'deterministic'
        assert {c['id'] for c in detail['capabilities']} <= capabilities
        assert detail['metrics'] and detail['theme']
    assert client.get('/api/v1/domains/unknown').status_code == 404
    assert client.post('/api/v1/domains/fintech/scenarios/camera/start', json={}).status_code == 404
    assert client.get('/openapi.json').json()['info']['version'] == '2.0.0'


@pytest.mark.parametrize('domain_id', ['identity','smart_city','fintech','tourism','industry','climate','open_innovation'])
def test_each_domain_through_real_api_websocket_and_history(client, domain_id):
    scenario = client.get(f'/api/v1/domains/{domain_id}/scenarios').json()[0]
    started = client.post(f"/api/v1/domains/{domain_id}/scenarios/{scenario['id']}/start",
                          json={'step_duration': .01})
    assert started.status_code == 201
    incident_id = started.json()['id']
    with client.websocket_connect(f'/ws/incidents/{incident_id}') as socket:
        sequences = []
        for _ in range(100):
            snapshot = socket.receive_json()
            record = snapshot['incident']
            sequences.append(snapshot['seq'])
            assert record['domain_id'] == domain_id
            assert record['status'] != 'FAILED', record.get('outcome')
            if record['report']:
                break
        else:
            pytest.fail('No completed report received')
    assert sequences == sorted(sequences)
    total = sum(n['critical'] for n in record['topology']['nodes'])
    assert record['status'] == 'CONTAINED'
    assert record['residual_impact']['score'] == 0
    assert all(s['online'] == total and s['total'] == total for s in record['samples'])
    assert all(a['state'] == 'COMPLETE' for a in record['agents'])
    report = client.get(f'/api/incidents/{incident_id}/report').json()
    assert report['domain_id'] == domain_id
    assert report['executive']['total_services'] == total
    assert report['technical']['metrics_after'] == record['metrics']
    assert report['technical']['network_actions'] == record['actions']
    assert report['technical']['reasoner_mode'] == 'deterministic'
    history = client.get(f'/api/incidents?domain_id={domain_id}').json()
    assert all(i['domain_id'] == domain_id for i in history)
    assert history[0]['id'] == incident_id
    reset = client.post(f'/api/incidents/{incident_id}/reset', json={}).json()
    assert reset['domain_id'] == domain_id
    assert reset['report'] == report
    assert all(n['state'] == 'ONLINE' for n in reset['topology']['nodes'])


def test_legacy_payload_defaults_preserve_existing_report(tmp_path):
    """V1 JSON blobs remain readable without a destructive SQLite migration."""
    from app.topology import build_topology
    from app.agents import initial_agents
    old = dict(id='GM-LEGACY', scenario_id='camera', title='Existing report', source='camera',
               mode='fast', auto_approve=True, step_duration=1.7,
               topology=build_topology().model_dump(mode='json'), agents=[a.model_dump() for a in initial_agents()])
    for key in ('service_roots', 'preferred_targets', 'required_trust'):
        old['topology'].pop(key)
    incident = Incident.model_validate(old)
    assert incident.domain_id == 'smart_city'
    assert len(incident.topology.nodes) == 14
    repo = Repository(f"sqlite:///{tmp_path/'legacy.db'}")
    try:
        repo.save(incident)
        assert repo.get(incident.id).model_dump() == incident.model_dump()
    finally:
        repo.engine.dispose()
