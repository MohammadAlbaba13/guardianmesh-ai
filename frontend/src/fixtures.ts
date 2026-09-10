import type { Asset, DomainDetail, Incident, Topology } from './types';
import { idleAgents } from './types';
export const testTopology:Topology={nodes:[
  {id:'camera',name:'IoT Security Camera',kind:'camera',critical:false,x:0,y:0},
  ...['hospital','emergency','energy','traffic_center','safety','control'].map((id,i)=>({id,name:id,kind:id,critical:true,x:i*100,y:100})),
].map(n=>({...n,zone:'test-zone',criticality:1,exposure:.8,protection:0,state:'ONLINE',operational:true,latency_ms:45} as Asset)),edges:[]};
export function testIncident():Incident {return {id:'GM-TEST',scenario_id:'camera',title:'Compromised IoT Camera',source:'camera',started_at:'2026-09-06T12:00:00Z',ended_at:null,status:'RUNNING',phase:'ATTACK',mode:'fast',auto_approve:true,step_duration:1.7,topology:structuredClone(testTopology),agents:structuredClone(idleAgents),classification:null,impact:null,residual_impact:null,plan:null,policy:null,approvals:[],actions:[],timeline:[{seq:1,timestamp:'2026-09-06T12:00:00Z',type:'INCIDENT_STARTED',agent:null,message:'Synthetic camera attack.'}],samples:[],report:null,outcome:null};}

export function testDomain(id='smart_city',serviceCount=6):DomainDetail {
  return {id,name:id==='smart_city'?'Smart Cities & Urban Safety':id.replaceAll('_',' '),theme:'Test challenge theme',value_proposition:'Protect domain services using network evidence.',tagline:id==='smart_city'?'Keep the city moving.':`Protect ${id} services.`,twin_title:'Operational digital twin',services_label:'CRITICAL SERVICES',risk_label:'SERVICE RISK',event_label:'EVENT',report_label:'Generate Incident Report',outcome_label:'Response verified',accent:'#83e3bc',icon:'network',
    topology:{nodes:structuredClone(testTopology.nodes.slice(0,serviceCount+1)),edges:[]},scenarios:[{id:id==='smart_city'?'camera':`${id}_event`,title:'Deterministic scenario',subtitle:'Recorded evidence',source:'camera',requires_approval:false,domain_id:id,category:'CYBER'}],capabilities:[{id:'qod',name:'Quality on Demand',description:'Simulated connectivity priority',conceptual:false,mode:'SIMULATED'}],metrics:[],provider:{name:'Local deterministic simulator',mode:'SIMULATED',simulated:true,requested:'simulated',notice:'No live network connectivity'},reasoner:{mode:'deterministic',requested:'deterministic',notice:'Deterministic safety'}};
}
export const testDomains=['identity','smart_city','fintech','tourism','industry','climate','open_innovation'].map(id=>testDomain(id));
