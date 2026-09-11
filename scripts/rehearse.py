"""Exercise the running local API/WS with deterministic incidents; never calls live providers.

Run from root: .venv/Scripts/python.exe scripts/rehearse.py
The current active run is not modified. Start from Reset Demo.
"""
import asyncio
import json
from pathlib import Path
import httpx
import websockets


async def main():
    evidence=[]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",timeout=10) as client:
        for domain in (await client.get('/api/v1/domains')).json():
            scenarios=(await client.get(f'/api/v1/domains/{domain["id"]}/scenarios')).json()
            for scenario in scenarios:
                response=await client.post(f'/api/v1/domains/{domain["id"]}/scenarios/{scenario["id"]}/start',json={
                    'step_duration':.02,'execution_mode':'SIMULATION','ai_mode':'deterministic'})
                response.raise_for_status();incident=response.json();last=0
                async with websockets.connect(f'ws://127.0.0.1:8000/ws/incidents/{incident["id"]}') as ws:
                    async with asyncio.timeout(30):
                        while True:
                            snapshot=json.loads(await ws.recv());incident=snapshot['incident']
                            assert snapshot['seq']>=last;last=snapshot['seq']
                            if incident['phase']=='COMPLETE':break
                            if incident['status']=='FAILED':raise AssertionError(incident['outcome'])
                assert incident['status']=='CONTAINED' and incident['residual_impact']['score']==0
                assert all(a['state']=='COMPLETE' for a in incident['agents'])
                assert all(n['operational'] for n in incident['topology']['nodes'] if n['critical'])
                assert all(a['result']['mode']=='SIMULATED' for a in incident['actions'])
                persisted=(await client.get(f'/api/incidents/{incident["id"]}/report')).json()
                assert persisted['technical']['timeline'][-1]['type']=='REPORT_GENERATED'
                evidence.append({'domain':domain['id'],'scenario':scenario['id'],'incident_id':incident['id'],
                    'status':incident['status'],'agents':len(incident['agents']),'events':last,
                    'critical_services':sum(n['critical'] for n in incident['topology']['nodes']),
                    'residual_risk':incident['residual_impact']['score'],'provider_modes':sorted({a['result']['mode'] for a in incident['actions']})})
                (await client.post(f'/api/incidents/{incident["id"]}/reset')).raise_for_status()
    path=Path(__file__).resolve().parents[1]/'docs'/'live-rehearsal.json'
    path.write_text(json.dumps(evidence,indent=2),encoding='utf8')
    print(f'{len(evidence)} API/WebSocket/report rehearsals PASS; {path}')


if __name__=='__main__':asyncio.run(main())
