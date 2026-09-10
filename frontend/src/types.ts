export type SecurityState = 'ONLINE'|'WARNING'|'COMPROMISED'|'AT_RISK'|'PROTECTED'|'ISOLATED'|'OFFLINE';
export interface Asset { id:string; name:string; kind:string; zone:string; critical:boolean; criticality:number; exposure:number; protection:number; state:SecurityState; operational:boolean; latency_ms:number; x:number; y:number }
export interface Link { id:string; source:string; target:string; kind:string; weight:number; propagates_threat:boolean; carries_service:boolean; enabled:boolean; state:'NORMAL'|'THREAT'|'PROTECTED'|'BLOCKED' }
export interface Topology { nodes:Asset[]; edges:Link[] }
export interface Scenario { id:string; title:string; subtitle:string; source:string; requires_approval:boolean }
export interface Technique { id:string; name:string; tactic:string; domain:string; explanation:string; url:string }
export interface Classification { threat_type:string; confidence:number; source:string; evidence:string[]; reasoning:string; techniques:Technique[] }
export interface AssetRisk { node_id:string; score:number; distance:number; path:string[]; critical:boolean; factors:Record<string,number> }
export interface Impact { score:number; severity:string; impacted:AssetRisk[]; critical_services:string[]; propagation_path:string[]; explanation:string }
export interface NetworkAction { id:string; kind:string; target:string; endpoint:string; rationale:string; expected_effect:string; status:'PENDING'|'EXECUTING'|'COMPLETE'|'FAILED'; result:Record<string,unknown>; executed_at:string|null }
export interface Plan { id:string; version:number; strategy:string; rationale:string; actions:NetworkAction[] }
export interface Policy { decision:'APPROVED'|'APPROVAL_REQUIRED'|'REJECTED'; reasons:string[]; rules:string[] }
export interface Approval { plan_id:string; plan_version:number; decision:'APPROVE'|'REJECT'; actor:'OPERATOR'|'DEMO_AUTOMATION'; timestamp:string }
export interface Agent { name:string; role:string; state:'IDLE'|'ANALYZING'|'COMPLETE'|'WAITING'|'EXECUTING'; finding:string }
export interface TimelineEvent { seq:number; timestamp:string; type:string; agent:string|null; message:string }
export interface Sample { step:number; online:number; risk:number; latency:number }
export interface Report { generated_at:string; executive:{ headline:string; what_happened:string; service_risk:string; response:string; actions_completed:number; availability:string; minimum_services_online:number; residual_risk:number|null; outcome:string; duration_seconds:number; simulation:boolean }; technical:Record<string,unknown> }
export interface Incident { id:string; scenario_id:string; title:string; source:string; started_at:string; ended_at:string|null; status:'RUNNING'|'PAUSED'|'AWAITING_APPROVAL'|'CONTAINED'|'RESET'|'FAILED'|'INTERRUPTED'; phase:string; mode:'fast'|'guided'; auto_approve:boolean; step_duration:number; topology:Topology; agents:Agent[]; classification:Classification|null; impact:Impact|null; residual_impact:Impact|null; plan:Plan|null; policy:Policy|null; approvals:Approval[]; actions:NetworkAction[]; timeline:TimelineEvent[]; samples:Sample[]; report:Report|null; outcome:string|null }
export interface IncidentSummary { id:string; title:string; status:string; started_at:string; has_report:boolean }
export interface Snapshot { type:'SNAPSHOT'; seq:number; incident:Incident }
export const idleAgents:Agent[] = [['Sentinel','Detect & classify'],['Impact','Trace service exposure'],['Response','Plan safe containment'],['Compliance','Enforce operational policy'],['Network','Execute simulated capabilities'],['Report','Explain the outcome']].map(([name,role])=>({name,role,state:'IDLE',finding:'Ready for incident telemetry.'}));
