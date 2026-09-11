import { useEffect, useRef, useState } from 'react';

import { CheckCircle2, Download, FileText, Printer, X } from 'lucide-react';

import { request } from '../api';

import type { Incident, IncidentSummary, Report } from '../types';



export function Reports({incident,onClose}:{incident:Incident|null;onClose:()=>void}) {

  const dialog=useRef<HTMLDialogElement>(null);

  const [tab,setTab]=useState<'executive'|'technical'>('executive');

  const [report,setReport]=useState<Report|null>(incident?.report??null);

  const [history,setHistory]=useState<IncidentSummary[]>([]);

  const [error,setError]=useState('');

  const loadGeneration=useRef(0);

  const [loading,setLoading]=useState(false);

  const [selected,setSelected]=useState(incident?.report?incident.id:'');

  useEffect(()=>{dialog.current?.showModal(); void request<IncidentSummary[]>('/incidents').then(rows=>setHistory(rows.filter(row=>row.has_report))).catch(()=>setError('Could not load incident history.'));},[]);

  const load=async(id:string)=>{const current=++loadGeneration.current;setSelected(id);setReport(null);setLoading(true);try{const value=await request<Report>(`/incidents/${encodeURIComponent(id)}/report`);if(current===loadGeneration.current){setReport(value);setError('');}}catch(e){if(current===loadGeneration.current)setError(String(e));}finally{if(current===loadGeneration.current)setLoading(false);}};

  const total=report?.executive.total_services??(report?.technical.topology as {nodes?:{critical:boolean}[]}|undefined)?.nodes?.filter(n=>n.critical).length??report?.executive.availability.match(/\/\s*(\d+)/)?.[1]??'—';

  return <dialog ref={dialog} className="report-dialog" onCancel={onClose} aria-labelledby="report-title"><div className="report-header"><div><span className="eyebrow">GUARDIANMESH AI · INCIDENT RECORD</span><h2 id="report-title">{report?.domain?.report_label??'Resilience, documented.'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close report"><X size={22}/></button></div><div className="report-tools"><label>Incident<select value={selected} onChange={event=>void load(event.target.value)}><option value="" disabled>Select an incident</option>{history.map(row=><option key={row.id} value={row.id}>{row.domain_id?`${row.domain_id.replaceAll('_',' ')} · `:''}{row.title} · {row.id}</option>)}{selected&&!history.some(r=>r.id===selected)&&<option value={selected}>{selected}</option>}</select></label><a className="button small" aria-disabled={!report} href={report?`/api/incidents/${encodeURIComponent(selected)}/report?download=true`:undefined} download={`${selected}-incident-report.json`}><Download size={15}/>Export JSON</a><button className="button small" onClick={()=>window.print()} disabled={!report}><Printer size={15}/>Print</button></div>{error&&<p role="alert">{error}</p>}<div className="report-tabs" role="tablist"><button role="tab" aria-selected={tab==='executive'} onClick={()=>setTab('executive')}>Executive summary</button><button role="tab" aria-selected={tab==='technical'} onClick={()=>setTab('technical')}>Technical report</button></div><div className="report-body">{!report?<div className="empty-feed"><FileText size={36}/><h3>{loading?'Loading incident evidence…':'No completed reports yet.'}</h3><p>Run a defense scenario, then return here to inspect its evidence.</p></div>:tab==='executive'?<><div className="report-domain-context"><span>{report.executive.domain_name??report.domain?.name??'Archived incident'}</span><p>{report.executive.theme??report.domain?.theme}</p><small>Network: {report.executive.provider_mode??(report.executive.simulation?'SIMULATED':'Unspecified')} · AI Reasoning: {(report.executive.reasoner_mode??'deterministic')==='local_llm'?'Local LLM':'Deterministic'}</small></div><div className="report-success"><CheckCircle2 size={30}/><h3>{report.executive.headline}</h3><p>{report.executive.availability} · {report.executive.duration_seconds.toFixed(1)} seconds elapsed</p></div><div className="report-metrics"><div><strong>{report.executive.minimum_services_online}/{total}</strong><span>Minimum services online</span></div><div><strong>{report.executive.actions_completed}</strong><span>Capabilities completed</span></div><div><strong>{report.executive.residual_risk ?? (report.technical.residual_impact as {score?:number} | undefined)?.score ?? '—'}</strong><span>Residual propagation risk</span></div></div>{!!report.executive.metrics_after?.length&&<div className="report-measurements"><h4>Modeled domain measurements</h4><table><thead><tr><th>Measurement</th><th>Before response</th><th>After response</th></tr></thead><tbody>{report.executive.metrics_after.map(metric=><tr key={metric.id}><th>{metric.label}</th><td>{report.executive.metrics_before?.find(before=>before.id===metric.id)?.value??'—'} {metric.unit}</td><td>{metric.value} {metric.unit}</td></tr>)}</tbody></table></div>}{[['What happened',report.executive.what_happened],['Service risk',report.executive.service_risk],['Response',report.executive.response],['Final outcome',report.executive.outcome]].map(([title,body])=><section className="report-section" key={title}><h4>{title}</h4><p>{body}</p></section>)}</>:<><p className="technical-intro">Complete incident evidence, graph-risk factors, agent decisions, policy results, approval history and executed network actions.</p><pre className="technical-report">{JSON.stringify(report.technical,null,2)}</pre></>}</div><div className="report-disclaimer">{report?.executive.simulation!==false?'LOCAL SIMULATION · Synthetic evidence and network actions · No live Nokia or CAMARA connectivity':'External QoD evidence in technical report; topology, metrics and containment remain simulated'}</div></dialog>;

}
