import { describe,it,expect,vi,afterEach } from 'vitest';
import { applySnapshot,request } from './api';
import { testIncident } from './fixtures';
describe('event state',()=>{
  it('applies the backend snapshot and ignores older sequence numbers',()=>{
    const current=testIncident();
    const next=structuredClone(current); next.timeline.push({...next.timeline[0],seq:2,type:'DEVICE_ISOLATED'});next.topology.nodes[0].state='ISOLATED';
    const updated=applySnapshot(current,{type:'SNAPSHOT',seq:2,incident:next});
    expect(updated?.topology.nodes[0].state).toBe('ISOLATED');
    expect(applySnapshot(updated,{type:'SNAPSHOT',seq:1,incident:current})).toBe(updated);
  });
  it('accepts a clean new incident with its own sequence',()=>{
    const current=testIncident();const next=testIncident();next.id='GM-NEW';
    expect(applySnapshot(current,{type:'SNAPSHOT',seq:1,incident:next})?.id).toBe('GM-NEW');
  });
});
describe('validated API requests',()=>{
  afterEach(()=>vi.unstubAllGlobals());
  it('sends JSON controls and surfaces backend conflicts',async()=>{
    const fetcher=vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Approval pending'})});vi.stubGlobal('fetch',fetcher);
    await expect(request('/incidents/GM-TEST/skip',{})).rejects.toThrow('Approval pending');
    expect(fetcher).toHaveBeenCalledWith('/api/incidents/GM-TEST/skip',expect.objectContaining({method:'POST',body:'{}'}));
  });
});
