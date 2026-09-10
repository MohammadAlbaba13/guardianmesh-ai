import type { CSSProperties } from 'react';
import { Building2, Fingerprint, Landmark, Compass, Factory, Leaf, Layers3, ArrowUpRight, Check, Cpu, Radio } from 'lucide-react';
import type { DomainDetail, DomainMetadata, Incident } from '../types';

const icons:Record<string,typeof Layers3>={identity:Fingerprint,fingerprint:Fingerprint,smart_city:Building2,city:Building2,building:Building2,fintech:Landmark,bank:Landmark,tourism:Compass,compass:Compass,industry:Factory,factory:Factory,climate:Leaf,leaf:Leaf,open_innovation:Layers3,layers:Layers3,network:Layers3};
export function DomainSelector({domains,selected,busy,onSelect}:{domains:DomainMetadata[];selected:string|undefined;busy:boolean;onSelect:(id:string)=>unknown}) {
  return <section className="domain-selection" aria-label="Select operational domain"><div className="domain-selection-heading"><div><span className="eyebrow">ONE INTELLIGENCE ENGINE</span><h2>Select operational domain</h2></div><span>{domains.length} environments · One programmable network</span></div><div className="domain-grid">{domains.map((domain,index)=>{const Icon=icons[domain.icon]??icons[domain.id]??Layers3;return <button key={domain.id} style={{'--domain-accent':domain.accent} as CSSProperties} className={`domain-card ${selected===domain.id?'is-selected':''}`} aria-pressed={selected===domain.id} aria-label={domain.name} onClick={()=>void onSelect(domain.id)} disabled={busy} title={domain.value_proposition}><div className="domain-card-top"><Icon size={23}/><span>{selected===domain.id?<Check size={14}/>:String(index+1).padStart(2,'0')}</span></div><strong>{domain.name}</strong><div className="domain-card-bottom">{selected===domain.id?'ACTIVE DOMAIN':'EXPLORE DOMAIN'}<ArrowUpRight size={12}/></div></button>;})}</div></section>;
}

export function RuntimeContext({domain,incident}:{domain:DomainDetail|null;incident:Incident|null}) {
  if(!domain) return null;
  const provider=incident?.provider_mode??domain.provider.mode;
  const reasoner=incident?.reasoner_mode??domain.reasoner.mode;
  return <div className="runtime-context" aria-label="Execution context"><span title={domain.provider.notice??undefined}><Radio size={13}/><b>Network provider</b>{provider}<small>{incident?.provider_name??domain.provider.name}</small></span><span title={incident?.reasoning?.fallback_reason??domain.reasoner.notice??undefined}><Cpu size={13}/><b>AI Reasoning:</b>{reasoner==='local_llm'?'Local LLM':'Deterministic'}{incident?.reasoning?.fallback_reason&&<small>Safe fallback</small>}</span><span className="runtime-policy"><Check size={13}/>Policy governed execution</span></div>;
}

