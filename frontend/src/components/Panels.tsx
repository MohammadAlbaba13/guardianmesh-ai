import { Activity, ArrowRight, Check, CheckCircle2, CircleDot, Clock3, FileText, Fingerprint, GitBranch, LoaderCircle, Radar, ShieldCheck, Terminal, Zap } from 'lucide-react';

import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from 'recharts';

import type { Incident, Agent, Topology, NetworkAction, DomainDetail } from '../types';



export function Continuity({topology,incident,domain}:{topology:Topology|null;incident:Incident|null;domain?:DomainDetail|null}) {

  const services=topology?.nodes.filter(n=>n.critical)??[];

  const online=services.filter(n=>n.operational).length;

  const total=services.length;

  const metrics=incident?.metrics??domain?.metrics??[];

  const samples=incident?.samples.length?incident.samples:[{step:0,online,risk:0,latency:0},{step:1,online,risk:0,latency:0}];

  return <><section className="continuity" aria-label="Service continuity"><div className="continuity-main"><div className="continuity-icon"><ShieldCheck size={26}/></div><div><div className="continuity-count"><strong>{topology?online:'–'}<span> / {total||'–'}</span></strong><span>{domain?.services_label??'CRITICAL SERVICES'}<br/>ONLINE</span></div><p>{incident?.status==='CONTAINED'?'Response verified. Essential services uninterrupted.':'Continuous protection for the services that matter.'}</p></div></div><div className="service-pills">{services.map(n=><span key={n.id} title={`${n.name}: ${n.state.replace('_',' ')}; ${n.operational?'online':'offline'}`}><i className={n.operational?'status-dot':'status-dot danger'}/>{n.name}</span>)}</div><div className="availability-chart"><div><span>Service availability</span><strong>{topology&&total?`${Math.round(online/total*100)}%`:'—'}</strong></div><ResponsiveContainer width="100%" height={36}><AreaChart data={samples}><YAxis hide domain={[0,total||1]}/><Tooltip contentStyle={{background:'#13212b',border:'1px solid #304554',color:'#e6eff5'}} labelFormatter={()=>'Recorded incident event'} formatter={(value)=>[`${value} / ${total}`,'Online']}/><Area type="stepAfter" dataKey="online" stroke="#7ee5bc" strokeWidth={2} fill="#7ee5bc" fillOpacity={.1} isAnimationActive={false}/></AreaChart></ResponsiveContainer></div></section>

  {!!metrics.length&&<section className="domain-metrics" aria-label="Domain measurements"><span className="modeled-metrics-label">SIMULATED DIGITAL TWIN METRICS</span>{metrics.map(metric=>{const before=incident?.metrics_before?.find(m=>m.id===metric.id);return <div key={metric.id} title={metric.description}><span>{metric.label}</span><strong>{metric.value}<small>{metric.unit}</small></strong>{before&&<p>Baseline {before.value} {before.unit}</p>}</div>;})}</section>}</>;

}



export const phases=[['ATTACK','Attack'],['DETECT','Detect'],['CLASSIFY','Classify'],['IMPACT','Predict impact'],['PLAN','Plan response'],['POLICY','Policy check'],['NETWORK','Network response'],['CONTAINED','Contained'],['COMPLETE','Report']];

export function Storyline({incident}:{incident:Incident|null}) {

  const index=incident?phases.findIndex(([id])=>id===(incident.phase==='APPROVAL'?'POLICY':incident.phase)):-1;

  return <div className="storyline" aria-label="Defense progress">{phases.map(([id,label],i)=><div key={id} className={`${i<index?'past':''} ${i===index?'current':''} ${i===0&&incident?'attack-stage':''}`}><span className="step-number">{i<index?<Check size={11}/>:String(i+1).padStart(2,'0')}</span><span>{id==='ATTACK'&&incident?.category&&incident.category!=='CYBER'?'Signal':id==='CONTAINED'&&incident?.category&&['ENVIRONMENTAL','OPERATIONAL'].includes(incident.category)?'Verified':label}</span>{i<phases.length-1&&<ArrowRight size={12} className="step-arrow"/>}</div>)}</div>;

}



export function ThreatPanel({incident,topology,approve,busy,onReport,domain}:{incident:Incident|null;topology:Topology|null;domain?:DomainDetail|null;approve:(d:'APPROVE'|'REJECT')=>unknown;busy:boolean;onReport:()=>void}) {

  const contained=incident?.status==='CONTAINED';

  const risk=incident?.residual_impact?.score??incident?.impact?.score??0;

  const source=topology?.nodes.find(n=>n.id===incident?.source);

  const sourceLabel=source?.state==='ISOLATED'?'ISOLATED':source?.session_restricted?'RESTRICTED':source?.verification_required?'VERIFY':contained?'VERIFIED':'SOURCE';

  const total=topology?.nodes.filter(n=>n.critical).length??0;

  const name=(id:string)=>topology?.nodes.find(n=>n.id===id)?.name??id;

  return <section className={`panel threat-panel ${contained?'contained':''}`} aria-label="Incident intelligence"><div className="panel-heading"><div><span className="eyebrow">{domain?.event_label??'INCIDENT'} INTELLIGENCE</span><h2>{contained?(domain?.outcome_label??'Containment verified'):incident?'Active investigation':'Defense standing by'}</h2></div><span className={`pill ${incident&&!contained?'coral':'green'}`}>{contained?'VERIFIED':incident?.status==='FAILED'?'FAILED':incident?.status==='AWAITING_APPROVAL'?'APPROVAL':incident?'ACTIVE':'ARMED'}</span></div>

    <div className="threat-content">{!incident?<><div className="ready-radar"><Radar size={54} strokeWidth={1}/><i/></div><h3>Ready to defend.</h3><p>Launch a scenario to follow evidence from first signal to a verified response.</p><div className="standby-list"><span><CheckCircle2 size={15}/>Six agents ready</span><span><CheckCircle2 size={15}/>Service protection policies loaded</span><span><CheckCircle2 size={15}/>Local network simulator connected</span></div></>:<>

      <div className="incident-id"><span>{incident.id}</span><span>{incident.mode==='fast'?'FAST PITCH':'GUIDED'}</span></div>

      <h3>{incident.title}</h3><div className="source-line"><Fingerprint size={16}/>{name(incident.source)}<span className={`pill ${contained?'green':'coral'}`}>{sourceLabel}</span></div>

      <div className="risk-row"><div><span className="eyebrow">{contained?'RESIDUAL RISK':domain?.risk_label??'PROJECTED SERVICE RISK'}</span><div className="risk-value"><strong>{incident.impact?risk:'—'}</strong><span>/ 100</span></div></div><span className={`risk-level ${contained?'green':'coral'}`}>{contained?'CONTAINED':incident.impact?.severity??'ASSESSING'}</span></div><div className="risk-meter"><i style={{width:`${risk}%`}}/></div>

      {incident.classification&&<div className="mitre-card"><span className="eyebrow">{incident.classification.techniques.length?`MITRE ATT&CK · ${incident.classification.techniques[0].domain}`:`${incident.category??'EVENT'} CLASSIFICATION`}</span>{incident.classification.techniques.length?incident.classification.techniques.map(t=><a href={t.url} target="_blank" rel="noreferrer" key={t.id}><code>{t.id}</code><span>{t.name}</span><ArrowRight size={14}/></a>):<h4>{incident.classification.threat_type.replaceAll('_',' ')}</h4>}<p>{incident.classification.techniques[0]?.tactic??'Evidence-based interpretation'} · {Math.round(incident.classification.confidence*100)}% rule confidence</p></div>}

      {incident.reasoning&&<details className="reasoning-card"><summary>Why this response <span>{incident.reasoning.mode==='local_llm'?'Local LLM':'Deterministic'}</span></summary><p>{incident.reasoning.interpretation}</p><p>{incident.reasoning.risk_rationale}</p><ul>{incident.reasoning.action_rationale.map((r,i)=><li key={i}>{r}</li>)}</ul><p>Constraints: {incident.policy?.rules.join(" · ")??"Policy evaluation pending"}</p>{incident.reasoning.fallback_reason&&<p className="fallback-notice">{incident.reasoning.fallback_reason}</p>}</details>}

      {incident.impact&&<div className="propagation"><span className="eyebrow"><GitBranch size={13}/>AFFECTED DEPENDENCIES</span><p>{incident.impact.propagation_path.map(name).join(' → ')}</p></div>}

      {incident.status==='AWAITING_APPROVAL'&&<div className="approval-card" role="alert"><h4><ShieldCheck size={18}/>Operator decision required</h4><p>{incident.plan?.rationale??'A shared infrastructure action needs an operator decision.'}</p>{incident.policy?.reasons.map(reason=><p key={reason}>{reason}</p>)}<p>{incident.manual_approval||incident.execution_mode!==undefined&&incident.execution_mode!=="SIMULATION"?"Reject prevents all proposed network execution.":"Reject to request the bounded fallback plan."}</p><ul>{incident.plan?.actions.filter(a=>a.kind==="qod").map(a=><li key={a.id}>Protect {name(a.target)} · QoD · {incident.execution_mode??"SIMULATION"}</li>)}</ul>{incident.auto_approve&&<span className="auto-label">Demo auto-approval enabled · simulated operator</span>}<div><button className="button primary small" disabled={busy||!!incident.approvals.length} onClick={()=>approve('APPROVE')}>Approve</button><button className="button small" disabled={busy||!!incident.approvals.length} onClick={()=>approve('REJECT')}>{incident.manual_approval||(incident.execution_mode!==undefined&&incident.execution_mode!=="SIMULATION")?"Reject":"Reject · safe fallback"}</button></div></div>}

      {contained&&<div className="containment-message"><ShieldCheck size={21}/><span>{source?.state==='ISOLATED'?'Source isolated.':source?.session_restricted?'Affected session restricted.':'Domain response verified.'}<br/><strong>{topology?.nodes.filter(n=>n.critical&&n.operational).length ?? 0} / {total} {(domain?.services_label??'critical services').replace(/ online$/i,'')} online.</strong></span></div>}

      {incident.report&&<button className="button report-button" onClick={onReport}><FileText size={16}/>{domain?.report_label??'Generate Incident Report'}<ArrowRight size={16}/></button>}

      {incident.status==='FAILED'&&<p role="alert" className="error-copy">{incident.outcome}</p>}

      {incident.status==='INTERRUPTED'&&<p className="error-copy">The backend restarted. Restart the scenario for a clean run.</p>}

    </>}</div>

  </section>;

}



const agentIcons:Record<string,typeof Radar>={Sentinel:Radar,Impact:GitBranch,Response:Zap,Compliance:ShieldCheck,Network:Activity,Report:FileText};

export function AgentPanel({agents,reasonerMode}:{agents:Agent[];reasonerMode?:string}) {

  return <section className="agents-section" aria-label="Six coordinated agents"><div className="section-heading"><div><span className="eyebrow">COORDINATED INTELLIGENCE</span><h2>Six agents. One defense.</h2></div><span className="micro-label">{reasonerMode==='local_llm'?'Local LLM advisory · deterministic safety':'Deterministic reasoning'} · shared incident context</span></div><div className="agent-grid">{agents.map((agent,index)=>{const Icon=agentIcons[agent.name]??Radar; const active=['ANALYZING','EXECUTING'].includes(agent.state);return <article key={agent.name} className={`agent-card agent-${agent.state.toLowerCase()}`}><div className="agent-card-top"><span className="agent-icon"><Icon size={19}/></span><span className="agent-number">0{index+1}</span><span className="agent-state">{active?<LoaderCircle size={12} className="spin"/>:agent.state==='COMPLETE'?<Check size={12}/>:<CircleDot size={11}/>} {agent.state}</span></div><h3>{agent.name}<span>Agent</span></h3><p className="agent-role">{agent.role}</p><p className="agent-finding">{agent.finding}</p></article>;})}</div></section>;

}



function ActionItem({action,domain}:{action:NetworkAction;domain?:DomainDetail|null}) {

  const capability=domain?.capabilities.find(c=>c.id===action.kind);

  const mode=String(action.result.execution_state??action.result.mode??'PENDING');

  return <div className="action-item"><span className={`action-status ${action.status.toLowerCase()}`}>{action.status==='COMPLETE'?<Check size={14}/>:action.status==='FAILED'?<CircleDot size={14}/>:<LoaderCircle size={14} className="spin"/>}</span><div><div className="endpoint"><span>{mode}</span><strong>{capability?.name??action.kind.replaceAll('_',' ')}</strong><small>{action.target.replaceAll('_',' ')}</small></div><p>{action.status==='COMPLETE'?String(action.result.summary):action.rationale}</p><details className="action-evidence"><summary>Capability evidence</summary><code>{action.endpoint}</code><pre>{JSON.stringify(action.result,null,2)}</pre></details></div></div>;

}

export function ActionPanel({incident,domain}:{incident:Incident|null;domain?:DomainDetail|null}) {

  return <section className="panel actions-panel"><div className="panel-heading"><div><span className="eyebrow">PROGRAMMABLE NETWORK & TRUST</span><h2>Network-as-Code actions</h2></div><Terminal size={20}/></div><div className="simulation-label"><span className="sim-square"/>{incident?.execution_mode??'SIMULATION'} REQUESTED · PER-ACTION PROVENANCE</div><div className="action-list" aria-label="Network actions">{incident?.actions.length?[...incident.actions].reverse().map(action=><ActionItem key={action.id} action={action} domain={domain}/>):<div className="capability-catalog">{domain?.capabilities.length?domain.capabilities.map(capability=><div key={capability.id} title={capability.description}><span>{capability.name}</span><small>{capability.mode}</small>{capability.conceptual&&<i>Internal capability</i>}</div>):<div className="empty-feed"><Terminal size={28}/><p>Network actions will appear here.</p></div>}</div>}</div><div className="feed-footer"><span>{incident?.actions.filter(a=>a.status==='COMPLETE').length??0} actions completed</span><span>External QoD evidence shown per action</span></div></section>;

}



export function TimelinePanel({incident}:{incident:Incident|null}) {

  return <section className="panel timeline-panel"><div className="panel-heading"><div><span className="eyebrow">EVIDENCE STREAM</span><h2>Incident timeline</h2></div><span className="pill neutral"><Clock3 size={12}/>{incident?.timeline.length??0} events</span></div><div className="timeline-list" aria-label="Incident timeline">{incident?.timeline.length?[...incident.timeline].reverse().map(event=><div className="timeline-item" key={event.seq}><div className={`timeline-mark ${event.type.includes('CONTAINED')||event.type.includes('GENERATED')?'success':''}`}/><div><div className="event-meta"><span>{event.agent??'SYSTEM'}</span><time>{new Date(event.timestamp).toLocaleTimeString('en-GB',{hour12:false})}</time><code>#{String(event.seq).padStart(2,'0')}</code></div><strong>{event.type.replaceAll('_',' ')}</strong><p>{event.message}</p></div></div>):<div className="empty-feed"><Activity size={28}/><p>Listening for the first signal.</p><span>Every decision and action is recorded in the local incident log.</span></div>}</div><div className="feed-footer"><span>Backend event stream</span><span>Ordered · persisted · replayable</span></div></section>;

}
