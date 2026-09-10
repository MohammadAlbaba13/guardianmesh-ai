import { useEffect, useState } from 'react';
import { ArrowUpRight, Check, ChevronRight, FileText, Globe2, LoaderCircle, Pause, Play, Radio, RefreshCw, RotateCcw, ShieldCheck, SkipForward, X, Zap } from 'lucide-react';
import { useGuardian } from './useGuardian';
import { idleAgents } from './types';
import { Topology } from './components/Topology';
import { Continuity, Storyline, ThreatPanel, AgentPanel, ActionPanel, TimelinePanel } from './components/Panels';
import { Reports } from './components/Reports';
import { DomainSelector, RuntimeContext } from './components/Domains';
import './styles.css';
import './polish.css';
import './domains.css';

export default function App() {
  const engine=useGuardian();
  const [scenario,setScenario]=useState('');
  const [mode,setMode]=useState<'fast'|'guided'>('fast');
  const [autoApprove,setAutoApprove]=useState(true);
  const [showReports,setShowReports]=useState(false);
  const incident=engine.incident;
  const domain=engine.domain;
  useEffect(()=>{if(!incident) setScenario(engine.scenarios[0]?.id??'');setShowReports(false);},[domain?.id]);
  useEffect(()=>{if(incident){setScenario(incident.scenario_id);setMode(incident.mode);setAutoApprove(incident.auto_approve);}},[incident?.id]);
  const active=!!incident&&(['RUNNING','PAUSED','AWAITING_APPROVAL'].includes(incident.status)||(incident.status==='CONTAINED'&&!incident.report));
  const canStart=engine.ready&&!engine.busy&&!active&&!!scenario;
  const launch=()=>incident?engine.restart(scenario,mode,autoApprove):engine.start(scenario,mode,autoApprove);
  const statusLabel=engine.connection==='live'?'Live event stream':engine.connection==='ready'?'Defense engine connected':engine.connection==='reconnecting'?'Reconnecting event stream':engine.connection==='offline'?'Engine offline':'Connecting';
  return <div className="app-shell"><header className="app-header"><a className="brand" href="/" aria-label="GuardianMesh AI command center"><span className="brand-mark"><ShieldCheck size={25}/></span><span>GuardianMesh<span className="brand-ai">AI</span><small>RESILIENCE & TRUST PLATFORM</small></span></a><div className="header-nav"><span className="nav-active">Command center</span><button onClick={()=>setShowReports(true)}><FileText size={15}/>Incident reports</button></div><div className="system-indicators"><span><i className={`status-dot ${engine.ready?'':'amber'}`}/>{engine.ready?'Resilience engine ready':'Connecting engine'}</span><span className="header-local"><Globe2 size={14}/>LOCAL PROTOTYPE</span></div></header>
    <main><div className="platform-intro"><div><span className="eyebrow">GUARDIANMESH AI</span><h1>Autonomous Multi-Domain<br className="hero-break"/> Resilience & Trust Platform</h1><p>One intelligence engine. Seven MENA domains. One programmable network.</p></div><div className="event-brand"><span>MENA IGNITE 2026</span><p>Policy-governed intelligence</p><small>Local, deterministic, auditable</small></div></div>
      <DomainSelector domains={engine.domains} selected={domain?.id} busy={engine.busy||!engine.ready} onSelect={engine.switchDomain}/>
      <div className="page-heading domain-heading"><div><div className="breadcrumb">OPERATIONS <ChevronRight size={12}/>{domain?.name??'CONNECTING'}</div><h2>{domain?.tagline??'Connecting to the resilience engine'}</h2><p>{domain?.value_proposition??'Loading operational domains from the backend.'}</p></div><div className="challenge-alignment"><span className="eyebrow">CHALLENGE ALIGNMENT</span><p>{domain?.theme??'Awaiting domain catalog'}</p></div></div>
      <RuntimeContext domain={domain} incident={incident}/>
      {engine.error&&<div className="error-banner" role="alert"><span>{engine.error}</span>{!engine.ready&&<button className="button small" onClick={()=>void engine.initialize()}><RefreshCw size={14}/>Reconnect</button>}<button className="icon-button" aria-label="Dismiss error" onClick={()=>engine.setError('')}><X size={16}/></button></div>}
      <section className="demo-controls" aria-label="Demo controls"><div className="scenario-control"><span className="control-icon"><Radio size={18}/></span><label htmlFor="scenario">{domain?.event_label??'EVENT'} SCENARIO<select id="scenario" value={scenario} onChange={e=>setScenario(e.target.value)} disabled={active||engine.busy}>{engine.scenarios.length?engine.scenarios.map((s,i)=><option value={s.id} key={s.id}>{String(i+1).padStart(2,'0')} · {s.title}</option>):<option value="">Loading scenarios</option>}</select></label></div><div className="mode-control" role="group" aria-label="Demo mode"><button className={mode==='fast'?'selected':''} disabled={active} onClick={()=>setMode('fast')} aria-pressed={mode==='fast'}><Zap size={14}/>Fast pitch<span>20–35 sec</span></button><button className={mode==='guided'?'selected':''} disabled={active} onClick={()=>setMode('guided')} aria-pressed={mode==='guided'}><Play size={13}/>Guided<span>~1 min</span></button></div><label className="approval-toggle" title="When a scenario requires approval, the decision is visibly recorded as DEMO_AUTOMATION."><input type="checkbox" checked={autoApprove} onChange={e=>setAutoApprove(e.target.checked)} disabled={active}/><span className="toggle-switch"><Check size={11}/></span><span>Demo auto-approval</span></label><button className="button primary run-button" disabled={!canStart} onClick={()=>void launch()}>{engine.busy?<LoaderCircle size={17} className="spin"/>:<Play size={16} fill="currentColor"/>}{active?'Autonomous defense running':'Run Autonomous Defense Demo'}</button></section>
      <Continuity topology={engine.topology} incident={incident} domain={domain}/><Storyline incident={incident}/>
      <div className="workspace-grid"><div className="network-column">{engine.topology?<Topology key={`${domain?.id}-${incident?.id??'standby'}`} topology={engine.topology} incident={incident} domain={domain}/>:<section className="panel twin-loading"><RadarPlaceholder/><h2>Connecting to the digital twin</h2><p>Waiting for the local defense engine.</p></section>}<div className="playback-bar"><div className="stream-state"><i className={`status-dot ${['live','ready'].includes(engine.connection)?'':'amber'}`}/>{statusLabel}{incident&&<span className="phase-label">{incident.status==='PAUSED'?'PAUSED':incident.phase.replace('_',' ')}</span>}</div><div className="playback-buttons"><button disabled={!incident||engine.busy||!['RUNNING','PAUSED'].includes(incident.status)} onClick={()=>void engine.control(incident?.status==='PAUSED'?'resume':'pause')}>{incident?.status==='PAUSED'?<Play size={14}/>:<Pause size={14}/>} {incident?.status==='PAUSED'?'Resume':'Pause'}</button><button disabled={!incident||engine.busy||incident.status!=='RUNNING'} onClick={()=>void engine.control('skip')}><SkipForward size={14}/>Skip</button><button disabled={!incident||engine.busy} onClick={()=>void engine.restart(scenario,mode,autoApprove)}><RotateCcw size={14}/>Restart</button><button disabled={!incident||engine.busy} onClick={()=>void engine.control('reset')}><RefreshCw size={14}/>Reset</button></div></div></div><ThreatPanel domain={domain} incident={incident} topology={engine.topology} approve={engine.approve} busy={engine.busy} onReport={()=>setShowReports(true)}/></div>
      <AgentPanel agents={incident?.agents??idleAgents} reasonerMode={incident?.reasoner_mode??domain?.reasoner.mode}/><div className="feeds-grid"><ActionPanel incident={incident} domain={domain}/><TimelinePanel incident={incident}/></div>
      <footer className="app-footer"><span><ShieldCheck size={14}/>GuardianMesh AI <i/>Policy-governed resilience</span><span>Offline-ready · Evidence-driven outcomes · Optional local AI</span><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API reference<ArrowUpRight size={13}/></a></footer>
    </main>{showReports&&<Reports incident={incident} onClose={()=>setShowReports(false)}/>}</div>;
}

function RadarPlaceholder(){return <div className="loading-symbol"><Radio size={32}/></div>;}
