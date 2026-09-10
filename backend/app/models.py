from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SecurityState(StrEnum):
    ONLINE = "ONLINE"
    WARNING = "WARNING"
    COMPROMISED = "COMPROMISED"
    AT_RISK = "AT_RISK"
    PROTECTED = "PROTECTED"
    ISOLATED = "ISOLATED"
    OFFLINE = "OFFLINE"


class Asset(Schema):
    id: str
    name: str
    kind: str
    zone: str
    critical: bool = False
    criticality: float = Field(ge=0, le=1)
    exposure: float = Field(ge=0, le=1)
    protection: float = Field(default=0, ge=0, le=1)
    state: SecurityState = SecurityState.ONLINE
    operational: bool = True
    latency_ms: int = 45
    x: int
    y: int


class Link(Schema):
    id: str
    source: str
    target: str
    kind: Literal["data", "control", "identity", "protected", "management"] = "data"
    weight: float = Field(default=1, ge=0, le=1)
    propagates_threat: bool = True
    carries_service: bool = True
    enabled: bool = True
    state: Literal["NORMAL", "THREAT", "PROTECTED", "BLOCKED"] = "NORMAL"


class Topology(Schema):
    nodes: list[Asset]
    edges: list[Link]


class Technique(Schema):
    id: str
    name: str
    tactic: str
    domain: str = "Enterprise"
    explanation: str
    url: str


class Classification(Schema):
    threat_type: str
    confidence: float
    source: str
    evidence: list[str]
    reasoning: str
    techniques: list[Technique]


class AssetRisk(Schema):
    node_id: str
    score: int
    distance: int
    path: list[str]
    critical: bool
    factors: dict[str, float]


class Impact(Schema):
    score: int = 0
    severity: str = "LOW"
    impacted: list[AssetRisk] = Field(default_factory=list)
    critical_services: list[str] = Field(default_factory=list)
    propagation_path: list[str] = Field(default_factory=list)
    explanation: str = "No threat propagation detected."


ActionKind = Literal["verify_location", "sim_swap", "reroute", "qod", "quarantine", "isolate_segment"]


class Action(Schema):
    id: str
    kind: ActionKind
    target: str
    endpoint: str
    rationale: str
    expected_effect: str
    status: Literal["PENDING", "EXECUTING", "COMPLETE", "FAILED"] = "PENDING"
    result: dict[str, Any] = Field(default_factory=dict)
    executed_at: str | None = None


class Plan(Schema):
    id: str
    version: int = 1
    strategy: str
    rationale: str
    actions: list[Action]


class PolicyDecision(Schema):
    decision: Literal["APPROVED", "APPROVAL_REQUIRED", "REJECTED"]
    reasons: list[str]
    rules: list[str]


class Approval(Schema):
    plan_id: str
    plan_version: int
    decision: Literal["APPROVE", "REJECT"]
    actor: Literal["OPERATOR", "DEMO_AUTOMATION"]
    timestamp: str = Field(default_factory=now)


class PolicyReview(Schema):
    plan_id: str
    plan_version: int
    timestamp: str = Field(default_factory=now)
    result: PolicyDecision


class AgentState(Schema):
    name: str
    role: str
    state: Literal["IDLE", "ANALYZING", "COMPLETE", "WAITING", "EXECUTING"] = "IDLE"
    finding: str = "Ready for incident telemetry."


class TimelineEvent(Schema):
    seq: int
    timestamp: str = Field(default_factory=now)
    type: str
    agent: str | None = None
    message: str


class ServiceSample(Schema):
    step: int
    online: int
    risk: int
    latency: int


class Report(Schema):
    generated_at: str = Field(default_factory=now)
    executive: dict[str, Any]
    technical: dict[str, Any]


class Telemetry(Schema):
    """Synthetic observations inspected by Sentinel's explicit detection rules."""
    remote_sessions: int = Field(default=0, ge=0)
    baseline_sessions: int = Field(default=2, ge=1)
    exploit_signature: bool = False
    sim_swap_minutes_ago: int | None = Field(default=None, ge=0)
    ownership_confirmed: bool = True
    location_matches: bool = True
    service_stop_requests: int = Field(default=0, ge=0)
    maintenance_window: bool = True


class Incident(Schema):
    id: str
    scenario_id: str
    title: str
    source: str
    started_at: str = Field(default_factory=now)
    ended_at: str | None = None
    status: Literal["RUNNING", "PAUSED", "AWAITING_APPROVAL", "CONTAINED", "RESET", "FAILED", "INTERRUPTED"] = "RUNNING"
    phase: str = "ATTACK"
    mode: Literal["fast", "guided"]
    auto_approve: bool
    step_duration: float
    topology: Topology
    agents: list[AgentState]
    telemetry: Telemetry = Field(default_factory=Telemetry)
    classification: Classification | None = None
    impact: Impact | None = None
    residual_impact: Impact | None = None
    plan: Plan | None = None
    policy: PolicyDecision | None = None
    plan_history: list[Plan] = Field(default_factory=list)
    policy_history: list[PolicyReview] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    samples: list[ServiceSample] = Field(default_factory=list)
    report: Report | None = None
    outcome: str | None = None


class StartRequest(Schema):
    mode: Literal["fast", "guided"] = "fast"
    auto_approve: bool = True
    step_duration: float | None = Field(default=None, ge=0.01, le=10)


class ApprovalRequest(Schema):
    plan_id: str
    plan_version: int
    decision: Literal["APPROVE", "REJECT"]
