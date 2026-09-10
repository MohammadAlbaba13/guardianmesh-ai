"""Read-only evidence collection from the running local GuardianMesh instance."""
import asyncio, hashlib, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'report-assets'
BASE = 'http://127.0.0.1:8000'

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2), encoding='utf-8')

def capture(incident_id, name):
    with httpx.Client(base_url=BASE) as client:
        response = client.get('/api/incidents/' + incident_id)
        response.raise_for_status()
        value = response.json()
        save(name + '.json', value)
        print(json.dumps({'id': value['id'], 'status': value['status'], 'phase': value['phase'], 'events':len(value['timeline']), 'report':bool(value['report'])}))

async def stream(incident_id):
    import websockets
    rows = []
    async with websockets.connect(BASE.replace('http:', 'ws:') + '/ws/incidents/' + incident_id, origin='http://127.0.0.1:5173') as ws:
        await ws.send('ping')
        async for raw in ws:
            payload = json.loads(raw)
            if payload['type'] == 'PONG':
                rows.append({'type':'PONG'})
            else:
                incident = payload['incident']
                rows.append({'received_at':datetime.now(timezone.utc).isoformat(), 'type':payload['type'], 'seq':payload['seq'], 'phase':incident['phase'], 'last_event':incident['timeline'][-1], 'online':sum(n['critical'] and n['operational'] for n in incident['topology']['nodes'])})
            save('websocket-runtime.json', rows)
            if payload.get('incident', {}).get('report'):
                print(f'Captured {len(rows)} live messages including complete report and ping response')
                return

def inspect():
    with httpx.Client(base_url=BASE) as client:
        for route, name in [('/api/health','health.json'),('/api/topology','topology.json'),('/api/scenarios','scenarios.json'),('/openapi.json','openapi.json')]:
            response=client.get(route); response.raise_for_status(); save(name,response.json())
    with sqlite3.connect(f'file:{ROOT / "backend/data/guardianmesh.db"}?mode=ro',uri=True) as db:
        tables=[r[0] for r in db.execute("select name from sqlite_master where type='table'")]
        save('database.json', {t:{'schema':list(db.execute(f'pragma table_info({t})')), 'rows':db.execute(f'select count(*) from {t}').fetchone()[0]} for t in tables})
    paths = [*ROOT.glob('backend/app/*.py'), *ROOT.glob('backend/tests/*.py'), *ROOT.glob('frontend/src/**/*'), ROOT/'compose.yaml', ROOT/'README.md']
    save('source-manifest.json', {'captured_at':datetime.now(timezone.utc).isoformat(), 'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}})
    print('Saved health, topology, scenarios, OpenAPI, SQLite schema/counts and source hashes')

if __name__ == '__main__':
    if sys.argv[1] == 'capture': capture(sys.argv[2],sys.argv[3])
    elif sys.argv[1] == 'stream': asyncio.run(stream(sys.argv[2]))
    elif sys.argv[1] == 'inspect': inspect()
