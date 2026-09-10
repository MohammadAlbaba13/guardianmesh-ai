import type { Incident, Snapshot } from './types';

export async function request<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch(`/api${path}`, { method:body===undefined?'GET':'POST', headers:body===undefined?{}:{'Content-Type':'application/json'}, body:body===undefined?undefined:JSON.stringify(body), signal:AbortSignal.timeout(10000) });
  if (!response.ok) {
    const error = await response.json().catch(()=>({detail:'Backend request failed.'}));
    throw new Error(typeof error.detail==='string'?error.detail:'The request could not be validated.');
  }
  return response.json() as Promise<T>;
}

export function applySnapshot(current:Incident|null, incoming:Snapshot):Incident|null {
  if (incoming.type!=='SNAPSHOT' || !incoming.incident?.id || !Array.isArray(incoming.incident.timeline)) return current;
  if (current?.id===incoming.incident.id && current.timeline.length>incoming.seq) return current;
  return incoming.incident;
}
