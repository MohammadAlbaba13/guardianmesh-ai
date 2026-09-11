"""Local-only release checks; SIMULATION is explicit on every started run."""
import asyncio
import json
from pathlib import Path
import httpx
import websockets


async def main():
    results = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000', timeout=15) as c:
        for path in ['/api/health', '/api/topology', '/api/scenarios', '/api/v1/domains',
                     '/api/v1/capabilities', '/api/v1/runtime', '/api/v1/diagnostics', '/openapi.json', '/docs']:
            r = await c.get(path)
            assert r.status_code == 200, (path, r.status_code)
            results.append({'test': path, 'status': 'PASS'})
        for payload in [None, {'step_duration': -1}, {'step_duration': 11}, {'execution_mode': 'FAKE'},
                        {'unknown': True}, {'severity': 'BAD'}]:
            r = await c.post('/api/scenarios/camera/start', json=payload)
            assert r.status_code == 422
        assert (await c.post('/api/scenarios/no-such-scenario/start', json={})).status_code == 404
        assert (await c.get('/api/v1/domains/no-such-domain')).status_code == 404
        assert (await c.post('/api/scenarios/camera/start', json={}, headers={'Origin': 'https://untrusted.example'})).status_code == 403
        assert (await c.get('/api/health', headers={'Host': 'untrusted.example'})).status_code == 400
        results.append({'test': 'Invalid/missing input, unknown identifiers, origin and host guards', 'status': 'PASS'})
        r = await c.post('/api/scenarios/camera/start', json={'execution_mode':'SIMULATION', 'step_duration':.1})
        r.raise_for_status()
        incident_id = r.json()['id']
        assert (await c.post('/api/scenarios/camera/start', json={'execution_mode':'SIMULATION'})).status_code == 409
        assert (await c.post(f'/api/incidents/{incident_id}/pause', json={})).json()['status'] == 'PAUSED'
        phase = (await c.get(f'/api/incidents/{incident_id}')).json()['phase']
        await asyncio.sleep(.2)
        assert (await c.get(f'/api/incidents/{incident_id}')).json()['phase'] == phase
        assert (await c.post(f'/api/incidents/{incident_id}/skip', json={})).status_code == 409
        assert (await c.post(f'/api/incidents/{incident_id}/resume', json={})).status_code == 200
        assert (await c.post(f'/api/incidents/{incident_id}/skip', json={})).status_code == 200
        async with websockets.connect(f'ws://127.0.0.1:8000/ws/incidents/{incident_id}') as ws:
            async with asyncio.timeout(20):
                while True:
                    record = json.loads(await ws.recv())['incident']
                    assert record['status'] != 'FAILED'
                    if record['phase'] == 'COMPLETE': break
        report = (await c.get(f'/api/incidents/{incident_id}/report?download=true'))
        assert report.status_code == 200 and 'attachment' in report.headers['content-disposition']
        assert report.json()['technical']['network_actions'] == record['actions']
        assert all(a['result']['mode']=='SIMULATED' for a in record['actions'])
        assert (await c.post(f'/api/incidents/{incident_id}/reset', json={})).json()['status'] == 'RESET'
        results.append({'test': 'Duplicate start, pause freeze, skip guard, resume, WS completion, report export, reset', 'status':'PASS'})
        for decision in ['APPROVE', 'REJECT']:
            started = await c.post('/api/scenarios/energy/start', json={'execution_mode':'SIMULATION','step_duration':.02,'auto_approve':False})
            started.raise_for_status()
            iid = started.json()['id']
            async with websockets.connect(f'ws://127.0.0.1:8000/ws/incidents/{iid}') as ws:
                async with asyncio.timeout(20):
                    while True:
                        record = json.loads(await ws.recv())['incident']
                        if record['status']=='AWAITING_APPROVAL': break
                assert not record['actions']
                body={'plan_id':record['plan']['id'],'plan_version':99,'decision':decision}
                assert (await c.post(f'/api/incidents/{iid}/approval',json=body)).status_code==409
                body['plan_version']=record['plan']['version']
                assert (await c.post(f'/api/incidents/{iid}/approval',json=body)).status_code==200
                async with asyncio.timeout(20):
                    while True:
                        record=json.loads(await ws.recv())['incident']
                        assert record['status']!='FAILED'
                        if record['phase']=='COMPLETE': break
                assert (any(a['kind']=='isolate_segment' for a in record['actions'])) == (decision=='APPROVE')
                assert record['residual_impact']['score']==0
            assert (await c.post(f'/api/incidents/{iid}/reset',json={})).status_code==200
            results.append({'test':f'Energy {decision}: stale approval blocked, correct resulting plan, continuity', 'status':'PASS'})
    Path(__file__).with_name('runtime-results.json').write_text(json.dumps(results,indent=2))
    print(f'{len(results)} runtime check groups PASS')


if __name__=='__main__': asyncio.run(main())
