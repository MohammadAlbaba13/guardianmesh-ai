import { useEffect, useState, useCallback, useRef } from 'react';
import { request, applySnapshot } from './api';
import type { DomainDetail, DomainMetadata, Incident, Snapshot } from './types';

const ACTIVE_INCIDENT = 'guardianmesh-active-incident';
const ACTIVE_DOMAIN = 'guardianmesh-domain';
const domainOf = (incident:Incident) => incident.domain_id ?? 'smart_city';

export function useGuardian() {
  const [domains,setDomains] = useState<DomainMetadata[]>([]);
  const [domain,setDomain] = useState<DomainDetail|null>(null);
  const [incident,setIncident] = useState<Incident|null>(null);
  const [error,setError] = useState('');
  const [ready,setReady] = useState(false);
  const [busy,setBusy] = useState(false);
  const [connection,setConnection] = useState<'ready'|'connecting'|'live'|'reconnecting'|'offline'>('connecting');
  const generation = useRef(0);
  const operationPending = useRef(false);
  const incidentRef = useRef<Incident|null>(null);
  const domainRef = useRef<DomainDetail|null>(null);
  const acceptIncident = useCallback((value:Incident|null) => {
    incidentRef.current=value;
    setIncident(value);
    if(value) localStorage.setItem(ACTIVE_INCIDENT,value.id);
    else localStorage.removeItem(ACTIVE_INCIDENT);
  },[]);
  const acceptDomain = useCallback((value:DomainDetail) => {
    domainRef.current=value; setDomain(value); localStorage.setItem(ACTIVE_DOMAIN,value.id);
  },[]);
  const fetchDomain = async(id:string) => {
    const value=await request<DomainDetail>(`/v1/domains/${encodeURIComponent(id)}`);
    if(value.id!==id || !Array.isArray(value.topology?.nodes) || !Array.isArray(value.scenarios)) throw new Error('The domain catalog response is invalid.');
    return value;
  };

  const initialize = useCallback(async()=>{
    const current=++generation.current;
    setReady(false);
    try {
      const catalog=await request<DomainMetadata[]>('/v1/domains');
      if(!Array.isArray(catalog)||!catalog.length) throw new Error('No operational domains are available.');
      const saved=localStorage.getItem(ACTIVE_INCIDENT);
      let restored:Incident|null=null;
      if(saved) {
        try { const record=await request<Incident>(`/incidents/${encodeURIComponent(saved)}`); if(record.status!=='RESET'&&catalog.some(d=>d.id===domainOf(record))) restored=record; }
        catch { if(current===generation.current) localStorage.removeItem(ACTIVE_INCIDENT); }
      }
      const selected=restored?domainOf(restored):localStorage.getItem(ACTIVE_DOMAIN);
      const id=catalog.find(d=>d.id===selected)?.id??catalog.find(d=>d.id==='smart_city')?.id??catalog[0].id;
      const detail=await fetchDomain(id);
      if(current!==generation.current) return;
      setDomains(catalog); acceptDomain(detail); acceptIncident(restored); setReady(true); setConnection('ready'); setError('');
    } catch(e) {
      if(current===generation.current) {setError(`The local resilience engine is unavailable. Start the backend, then reconnect. ${e instanceof Error?e.message:''}`); setConnection('offline');}
    }
  },[acceptDomain,acceptIncident]);
  useEffect(()=>{void initialize(); return()=>{generation.current++;};},[initialize]);

  const incidentId=incident?.id;
  useEffect(()=>{
    if(!incidentId) return;
    let disposed=false;
    let socket:WebSocket;
    let retry:ReturnType<typeof setTimeout>;
    const current=()=>!disposed&&incidentRef.current?.id===incidentId;
    const connect=()=>{
      if(!current()) return;
      setConnection('connecting');
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/incidents/${incidentId}`);
      socket.onopen=()=>{if(current()) setConnection('live');};
      socket.onmessage=event=>{
        if(!current()) return;
        try {
          const data=JSON.parse(event.data) as Snapshot;
          if(data.type!=='SNAPSHOT') return;
          if(!data.incident?.id||!Array.isArray(data.incident.timeline)) throw new Error('Invalid snapshot');
          if(data.incident.id!==incidentId||domainOf(data.incident)!==domainRef.current?.id) return;
          if(data.incident.status==='RESET') {acceptIncident(null);setConnection('ready');}
          else acceptIncident(applySnapshot(incidentRef.current,data));
        } catch { setError('An invalid live event was ignored. Reconnect to resynchronize.'); }
      };
      socket.onerror=()=>socket.close();
      socket.onclose=()=>{if(current()){setConnection('reconnecting');retry=setTimeout(connect,1500);}};
    };
    connect();
    return ()=>{disposed=true;clearTimeout(retry);socket?.close();};
  },[incidentId,acceptIncident]);

  const perform = async<T,>(operation:()=>Promise<T>):Promise<T|undefined>=>{
    if(operationPending.current) return;
    operationPending.current=true; setBusy(true); setError('');
    try {return await operation();}
    catch(e) {setError(e instanceof Error?e.message:'The operation failed.');}
    finally {operationPending.current=false;setBusy(false);}
  };
  const switchDomain = async(id:string)=>perform(async()=>{
    if(id===domainRef.current?.id || !domains.some(d=>d.id===id)) return;
    const current=++generation.current;
    const previous=incidentRef.current;
    // Reset on the server before leaving: only one shared engine may be active.
    if(previous) await request<Incident>(`/incidents/${previous.id}/reset`,{});
    if(current!==generation.current) return;
    acceptIncident(null); setReady(false); setConnection('connecting');
    const detail=await fetchDomain(id);
    if(current!==generation.current) return;
    acceptDomain(detail); setReady(true); setConnection('ready');
  });
  const startRun = async(scenario:string,mode:'fast'|'guided',auto:boolean)=>{
    const selected=domainRef.current;
    if(!selected||!selected.scenarios.some(s=>s.id===scenario)) throw new Error('Select a scenario in the current domain.');
    const current=generation.current;
    const value=await request<Incident>(`/v1/domains/${selected.id}/scenarios/${encodeURIComponent(scenario)}/start`,{mode,auto_approve:auto});
    if(current!==generation.current) return;
    if(domainOf(value)!==selected.id) throw new Error('The incident response belongs to a different domain.');
    acceptIncident(value); return value;
  };
  const start = (scenario:string,mode:'fast'|'guided',auto:boolean)=>perform(()=>startRun(scenario,mode,auto));
  const control = (command:'pause'|'resume'|'skip'|'reset')=>perform(async()=>{
    const active=incidentRef.current;
    if(!active) return;
    const value=await request<Incident>(`/incidents/${active.id}/${command}`,{});
    if(incidentRef.current?.id!==active.id) return;
    if(command==='reset') {acceptIncident(null);setConnection('ready');}
    else acceptIncident(applySnapshot(incidentRef.current,{type:'SNAPSHOT',seq:value.timeline.length,incident:value}));
    return value;
  });
  const restart = (scenario:string,mode:'fast'|'guided',auto:boolean)=>perform(async()=>{
    const active=incidentRef.current;
    if(active) {await request<Incident>(`/incidents/${active.id}/reset`,{});acceptIncident(null);}
    return startRun(scenario,mode,auto);
  });
  const approve = (decision:'APPROVE'|'REJECT')=>perform(async()=>{
    const active=incidentRef.current;
    if(!active?.plan) return;
    const value=await request<Incident>(`/incidents/${active.id}/approval`,{plan_id:active.plan.id,plan_version:active.plan.version,decision});
    if(incidentRef.current?.id===active.id) acceptIncident(applySnapshot(incidentRef.current,{type:'SNAPSHOT',seq:value.timeline.length,incident:value}));
  });
  return {domains,domain,switchDomain,topology:incident?.topology??domain?.topology??null,scenarios:domain?.scenarios??[],incident,error,setError,ready,busy,connection,start,control,restart,approve,initialize};
}
