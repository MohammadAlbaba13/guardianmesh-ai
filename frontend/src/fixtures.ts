import type { Asset, Incident, Topology } from './types';
import { idleAgents } from './types';
export const testTopology:Topology={nodes:[
  {id:'camera',name:'IoT Security Camera',kind:'camera',critical:false,x:0,y:0},
  ...['hospital','emergency','energy','traffic_center','safety','control'].map((id,i)=>({id,name:id,kind:id,critical:true,x:i*100,y:100})),
].map(n=>({...n,zone:'test-zone',criticality:1,exposure:.8,protection:0,state:'ONLINE',operational:true,latency_ms:45} as Asset)),edges:[]};
export function testIncident():Incident {return {id:'GM-TEST',scenario_id:'camera',title:'Compromised IoT Camera',source:'camera',started_at:'2026-09-06T12:00:00Z',ended_at:null,status:'RUNNING',phase:'ATTACK',mode:'fast',auto_approve:true,step_duration:1.7,topology:structuredClone(testTopology),agents:structuredClone(idleAgents),classification:null,impact:null,residual_impact:null,plan:null,policy:null,approvals:[],actions:[],timeline:[{seq:1,timestamp:'2026-09-06T12:00:00Z',type:'INCIDENT_STARTED',agent:null,message:'Synthetic camera attack.'}],samples:[],report:null,outcome:null};}
