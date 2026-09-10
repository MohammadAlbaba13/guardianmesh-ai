import { useEffect, useState, useCallback, useRef } from 'react';
import { request, applySnapshot } from './api';
import type { Incident, Scenario, Topology, Snapshot } from './types';

export function useGuardian() {
  const [topology,setTopology] = useState<Topology|null>(null);
  const [scenarios,setScenarios] = useState<Scenario[]>([]);
  const [incident,setIncident] = useState<Incident|null>(null);
  const [error,setError] = useState('');
  const [ready,setReady] = useState(false);
  const [busy,setBusy] = useState(false);
  const [connection,setConnection] = useState<'ready'|'connecting'|'live'|'reconnecting'|'offline'>('connecting');
  const initializationGeneration=useRef(0);

  const initialize = useCallback(async()=>{
    const generation=++initializationGeneration.current;
    setReady(false);
    try {
      const [twin,catalog] = await Promise.all([request<Topology>('/topology'),request<Scenario[]>('/scenarios')]);
      const saved = localStorage.getItem('guardianmesh-active-incident');
      let restored:Incident|null=null;
      if(saved) {
        try { const record=await request<Incident>(`/incidents/${encodeURIComponent(saved)}`); if(record.status!=='RESET') restored=record; }
        catch { if(generation===initializationGeneration.current) localStorage.removeItem('guardianmesh-active-incident'); }
      }
      if(generation!==initializationGeneration.current) return;
      setTopology(twin); setScenarios(catalog); setIncident(restored); setReady(true); setConnection('ready'); setError('');
    } catch { if(generation===initializationGeneration.current) {setError('The local defense engine is unavailable. Start the backend, then reconnect.'); setConnection('offline');} }
  },[]);
  useEffect(()=>{void initialize();return()=>{initializationGeneration.current++;};},[initialize]);

  const incidentId=incident?.id;
  useEffect(()=>{
    if(!incidentId) return;
    let disposed=false;
    let socket:WebSocket;
    let retry:ReturnType<typeof setTimeout>;
    const connect=()=>{
      if(disposed) return;
      setConnection('connecting');
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/incidents/${incidentId}`);
      socket.onopen=()=>{if(!disposed) setConnection('live');};
      socket.onmessage=event=>{
        if(disposed) return;
        try {
          const data=JSON.parse(event.data) as Snapshot;
          if(data.type==='SNAPSHOT' && data.incident.id===incidentId) {
            if(data.incident.status==='RESET') {setIncident(null);localStorage.removeItem('guardianmesh-active-incident');setConnection('ready');}
            else setIncident(current=>applySnapshot(current,data));
          }
        } catch { setError('An invalid live event was ignored. Reconnect to resynchronize.'); }
      };
      socket.onerror=()=>socket.close();
      socket.onclose=()=>{
        if(disposed) return;
        setConnection('reconnecting');
        retry=setTimeout(connect,1500);
      };
    };
    connect();
    return ()=>{disposed=true;clearTimeout(retry);socket?.close();};
  },[incidentId]);

  const perform = async<T,>(operation:()=>Promise<T>):Promise<T|undefined>=>{
    setBusy(true); setError('');
    try {return await operation();}
    catch(e) {setError(e instanceof Error?e.message:'The operation failed.');}
    finally {setBusy(false);}
  };
  const start = async(scenario:string,mode:'fast'|'guided',auto:boolean)=>perform(async()=>{
    const value=await request<Incident>(`/scenarios/${scenario}/start`,{mode,auto_approve:auto});
    localStorage.setItem('guardianmesh-active-incident',value.id); setIncident(value); return value;
  });
  const control = async(command:'pause'|'resume'|'skip'|'reset')=>{
    if(!incident) return;
    return perform(async()=>{
      const value=await request<Incident>(`/incidents/${incident.id}/${command}`,{});
      if(command==='reset') {setIncident(null);localStorage.removeItem('guardianmesh-active-incident');setConnection('ready');}
      else setIncident(current=>applySnapshot(current,{type:'SNAPSHOT',seq:value.timeline.length,incident:value}));
      return value;
    });
  };
  const restart=async(scenario:string,mode:'fast'|'guided',auto:boolean)=>{
    if(incident) {const reset=await control('reset'); if(!reset) return;}
    return start(scenario,mode,auto);
  };
  const approve=async(decision:'APPROVE'|'REJECT')=>{
    if(!incident?.plan) return;
    return perform(async()=>{
      const value=await request<Incident>(`/incidents/${incident.id}/approval`,{plan_id:incident.plan!.id,plan_version:incident.plan!.version,decision});
      setIncident(current=>applySnapshot(current,{type:'SNAPSHOT',seq:value.timeline.length,incident:value}));
    });
  };
  return {topology:incident?.topology??topology,scenarios,incident,error,setError,ready,busy,connection,start,control,restart,approve,initialize};
}
