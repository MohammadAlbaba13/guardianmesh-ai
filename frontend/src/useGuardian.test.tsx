import { renderHook,act,waitFor,cleanup } from '@testing-library/react';
import { vi,it,expect,afterEach } from 'vitest';
import { useGuardian } from './useGuardian';
import { testIncident,testDomain,testDomains } from './fixtures';
class FakeSocket {
  static instances:FakeSocket[]=[];
  onopen:(()=>void)|null=null;onmessage:((event:{data:string})=>void)|null=null;onerror:(()=>void)|null=null;onclose:(()=>void)|null=null;
  constructor(public url:string){FakeSocket.instances.push(this);}
  close(){}
}
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals();FakeSocket.instances=[];});
it('starts a scenario, streams topology state, controls pause/resume and resets',async()=>{
  const incident=testIncident();
  const fetcher=vi.fn(async(url:string)=>{
    let data:unknown=incident;
    if(url.endsWith('/v1/domains')) data=testDomains;
    if(url.endsWith('/v1/domains/smart_city')) data=testDomain();
    if(url.endsWith('/pause')) data={...incident,status:'PAUSED'};
    if(url.endsWith('/resume')) data={...incident,status:'RUNNING'};
    if(url.endsWith('/reset')) data={...incident,status:'RESET'};
    return {ok:true,json:async()=>structuredClone(data)};
  });
  vi.stubGlobal('fetch',fetcher);vi.stubGlobal('WebSocket',FakeSocket);
  const {result}=renderHook(()=>useGuardian());
  await waitFor(()=>expect(result.current.ready).toBe(true));
  await act(()=>result.current.start('camera','fast',true));
  expect(result.current.incident?.id).toBe('GM-TEST');
  const socket=FakeSocket.instances[0];
  act(()=>socket.onopen?.());expect(result.current.connection).toBe('live');
  incident.topology.nodes[0].state='COMPROMISED';
  act(()=>socket.onmessage?.({data:JSON.stringify({type:'SNAPSHOT',seq:1,incident})}));
  expect(result.current.topology?.nodes[0].state).toBe('COMPROMISED');
  await act(()=>result.current.control('pause'));expect(result.current.incident?.status).toBe('PAUSED');
  await act(()=>result.current.control('resume'));expect(result.current.incident?.status).toBe('RUNNING');
  await act(()=>result.current.control('reset'));expect(result.current.incident).toBeNull();
  expect(localStorage.getItem('guardianmesh-active-incident')).toBeNull();
});
it('shows a useful connection failure rather than a fake live twin',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('offline')));
  const {result}=renderHook(()=>useGuardian());
  await waitFor(()=>expect(result.current.connection).toBe('offline'));
  expect(result.current.ready).toBe(false);expect(result.current.error).toContain('Start the backend');
});
it('keeps Run unavailable until the saved incident is restored',async()=>{
  localStorage.setItem('guardianmesh-active-incident','GM-TEST');
  let release:(value:unknown)=>void=()=>{};
  const restored=new Promise(resolve=>{release=resolve;});
  vi.stubGlobal('WebSocket',FakeSocket);
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/v1/domains')?testDomains:url.endsWith('/v1/domains/smart_city')?testDomain():restored})));
  const {result}=renderHook(()=>useGuardian());
  await act(async()=>{await Promise.resolve();});
  expect(result.current.ready).toBe(false);
  await act(async()=>{release(testIncident());});
  await waitFor(()=>expect(result.current.ready).toBe(true));
  expect(result.current.incident?.id).toBe('GM-TEST');
});

it('switches domains after resetting the old incident and ignores its late WebSocket snapshots',async()=>{
  const incident=testIncident();
  const fetcher=vi.fn(async(url:string)=>({ok:true,json:async()=>{
    if(url.endsWith('/v1/domains')) return testDomains;
    const match=url.match(/\/v1\/domains\/(\w+)$/);
    if(match) return testDomain(match[1],match[1]==='fintech'?4:6);
    return structuredClone(incident);
  }}));
  vi.stubGlobal('fetch',fetcher);vi.stubGlobal('WebSocket',FakeSocket);
  const {result}=renderHook(()=>useGuardian());
  await waitFor(()=>expect(result.current.ready).toBe(true));
  await act(()=>result.current.start('camera','fast',true));
  const oldSocket=FakeSocket.instances[0];
  await act(()=>result.current.switchDomain('fintech'));
  expect(fetcher).toHaveBeenCalledWith('/api/incidents/GM-TEST/reset',expect.objectContaining({method:'POST'}));
  expect(result.current.domain?.id).toBe('fintech');
  expect(result.current.incident).toBeNull();
  expect(result.current.topology?.nodes.filter(n=>n.critical)).toHaveLength(4);
  act(()=>oldSocket.onmessage?.({data:JSON.stringify({type:'SNAPSHOT',seq:1,incident})}));
  expect(result.current.incident).toBeNull();
  expect(localStorage.getItem('guardianmesh-domain')).toBe('fintech');
  await act(()=>result.current.start('camera','fast',true));
  expect(result.current.error).toContain('Select a scenario in the current domain');
});

it('restores the recorded incident domain ahead of a stale saved domain preference',async()=>{
  const incident={...testIncident(),domain_id:'identity',scenario_id:'identity_event'};
  localStorage.setItem('guardianmesh-active-incident',incident.id);
  localStorage.setItem('guardianmesh-domain','smart_city');
  vi.stubGlobal('WebSocket',FakeSocket);
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/v1/domains')?testDomains:url.endsWith('/v1/domains/identity')?testDomain('identity',4):incident})));
  const {result}=renderHook(()=>useGuardian());
  await waitFor(()=>expect(result.current.ready).toBe(true));
  expect(result.current.domain?.id).toBe('identity');
  expect(result.current.incident?.scenario_id).toBe('identity_event');
});

it('preserves the active incident when switching cannot safely reset the backend',async()=>{
  vi.stubGlobal('WebSocket',FakeSocket);
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:!url.endsWith('/reset'),json:async()=>url.endsWith('/reset')?{detail:'The reset failed'}:url.endsWith('/v1/domains')?testDomains:url.endsWith('/v1/domains/smart_city')?testDomain():testIncident()})));
  const {result}=renderHook(()=>useGuardian());
  await waitFor(()=>expect(result.current.ready).toBe(true));
  await act(()=>result.current.start('camera','fast',true));
  await act(()=>result.current.switchDomain('climate'));
  expect(result.current.domain?.id).toBe('smart_city');
  expect(result.current.incident?.id).toBe('GM-TEST');
  expect(result.current.error).toBe('The reset failed');
});
