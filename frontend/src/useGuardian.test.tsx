import { renderHook,act,waitFor,cleanup } from '@testing-library/react';
import { vi,it,expect,afterEach } from 'vitest';
import { useGuardian } from './useGuardian';
import { testIncident,testTopology } from './fixtures';
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
    if(url.endsWith('/topology')) data=testTopology;
    if(url.endsWith('/scenarios')) data=[{id:'camera',title:'Camera'}];
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
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('/topology')?testTopology:url.endsWith('/scenarios')?[]:restored})));
  const {result}=renderHook(()=>useGuardian());
  await act(async()=>{await Promise.resolve();});
  expect(result.current.ready).toBe(false);
  await act(async()=>{release(testIncident());});
  await waitFor(()=>expect(result.current.ready).toBe(true));
  expect(result.current.incident?.id).toBe('GM-TEST');
});
