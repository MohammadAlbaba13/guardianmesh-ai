"""Check report assertions against captured real incident payloads."""
import json
from datetime import datetime
from pathlib import Path
import httpx

out=Path(__file__).parent/'report-assets'
def read(name):return json.loads((out/name).read_text(encoding='utf-8-sig'))
def seconds(start,end):return round((datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(),3)
summary={}
for label,filename in [('camera_fast','camera-fast-final.json'),('camera_guided','camera-guided-uninterrupted.json'),('camera_walkthrough','camera-guided-final.json'),('identity','identity-final.json'),('energy_approve','energy-approve-final.json'),('energy_reject','energy-reject-final.json')]:
    value=read(filename); report=value['report']; tech=report['technical']; exe=report['executive']
    assert tech['final_state']=='CONTAINED'
    assert exe['minimum_services_online']==6
    assert tech['source_asset']['state']=='ISOLATED'
    assert tech['residual_impact']['score']==0
    assert all(a['state']=='COMPLETE' for a in tech['agent_decisions'])
    assert all(a['status']=='COMPLETE' and a['result']['simulated'] for a in tech['network_actions'])
    assert [e['seq'] for e in tech['timeline']]==list(range(1,len(tech['timeline'])+1))
    summary[label]={'id':value['id'],'snapshot_status':value['status'],'report_final_state':tech['final_state'],'started_at':tech['started_at'],'contained_at':tech['ended_at'],'report_at':report['generated_at'],'containment_seconds':seconds(tech['started_at'],tech['ended_at']),'report_seconds':seconds(tech['started_at'],report['generated_at']),'peak_risk':tech['initial_impact']['score'],'residual_risk':tech['residual_impact']['score'],'critical_services_exposed':len(tech['initial_impact']['critical_services']),'minimum_online':exe['minimum_services_online'],'actions':len(tech['network_actions']),'events':len(tech['timeline']),'approval':tech['approval_history'],'plan_versions':[p['version'] for p in tech['plan_history']]}
assert read('energy-approve-before.json')['actions']==[]
assert summary['energy_approve']['approval'][0]['decision']=='APPROVE'
assert summary['energy_reject']['approval'][0]['decision']=='REJECT'
assert summary['energy_reject']['plan_versions']==[1,2]
assert not any(a['kind']=='isolate_segment' for a in read('energy-reject-final.json')['report']['technical']['network_actions'])
camera=read('camera-fast-final.json');hospital=next(n for n in camera['topology']['nodes'] if n['id']=='hospital')
assert hospital['latency_ms']==8 and hospital['state']=='PROTECTED'
assert all(s['online']==6 for s in camera['samples'])
assert not any(e['type'].startswith('DEMO_') for e in camera['timeline'])
stream=read('websocket-runtime.json')
assert any(r['type']=='PONG' for r in stream)
assert stream[-1]['last_event']['type']=='REPORT_GENERATED'
assert all(r.get('online',6)==6 for r in stream)
seqs=[r['seq'] for r in stream if 'seq' in r]
assert seqs==sorted(seqs)
with httpx.Client() as client:
    response=client.get(f'http://127.0.0.1:8000/api/incidents/{camera["id"]}/report?download=true')
    assert response.status_code==200 and response.json()['technical']['incident_id']==camera['id']
    assert 'attachment' in response.headers['content-disposition']
    summary['json_export']={'status':response.status_code,'content_disposition':response.headers['content-disposition'],'matches_incident':True}
summary['websocket']={'messages':len(stream),'ordered':True,'ping_pong':True,'last_sequence':seqs[-1]}
summary['console']=read('browser-console.json')
(out/'runtime-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
