import asyncio
import contextlib
import logging
import time
from uuid import uuid4
from .models import Incident, StartRequest, ApprovalRequest, Approval, PolicyReview, TimelineEvent, ServiceSample, SecurityState, now
from .scenarios import SCENARIOS, scenario_telemetry
from .topology import build_topology, asset, online_services, isolate, protect, continuity_verified
from .agents import initial_agents, SentinelAgent, ImpactAgent, ResponseAgent, ComplianceAgent, NetworkAgent, ReportAgent
from .provider import SimulatedNetworkProvider
from .persistence import Repository

log = logging.getLogger("guardianmesh.engine")


class Conflict(Exception):
    pass


class SimulationEngine:
    def __init__(self, repository: Repository, provider=None):
        self.repository = repository
        self.provider = provider or SimulatedNetworkProvider()
        self.current: Incident | None = None
        self.task: asyncio.Task | None = None
        self.lock = asyncio.Lock()
        self.resume_gate = asyncio.Event()
        self.resume_gate.set()
        self.skip_gate = asyncio.Event()
        self.approval_gate = asyncio.Event()
        self.subscribers: dict[str, set[asyncio.Queue]] = {}

    def get(self, incident_id: str) -> Incident:
        if self.current and self.current.id == incident_id:
            return self.current
        incident = self.repository.get(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        return incident

    def snapshot(self, incident: Incident) -> dict:
        return {"type": "SNAPSHOT", "seq": len(incident.timeline), "incident": incident.model_dump(mode="json")}

    def subscribe(self, incident_id: str) -> asyncio.Queue:
        incident = self.get(incident_id)
        queue = asyncio.Queue(maxsize=8)
        self.subscribers.setdefault(incident_id, set()).add(queue)
        queue.put_nowait(self.snapshot(incident))
        return queue

    def unsubscribe(self, incident_id: str, queue: asyncio.Queue):
        self.subscribers.get(incident_id, set()).discard(queue)

    def publish(self, incident: Incident):
        payload = self.snapshot(incident)
        for queue in self.subscribers.get(incident.id, set()):
            if queue.full():
                queue.get_nowait()  # Snapshots contain the full ordered timeline; coalescing loses no state.
            queue.put_nowait(payload)

    def emit(self, incident: Incident, event_type: str, message: str, agent: str | None = None):
        incident.timeline.append(TimelineEvent(seq=len(incident.timeline)+1, type=event_type, message=message, agent=agent))
        critical = [n for n in incident.topology.nodes if n.critical]
        risk = incident.residual_impact.score if incident.residual_impact else incident.impact.score if incident.impact else 0
        incident.samples.append(ServiceSample(step=len(incident.timeline), online=online_services(incident.topology), risk=risk,
                                             latency=round(sum(n.latency_ms for n in critical)/len(critical))))
        if event_type == "REPORT_GENERATED":
            incident.report = ReportAgent().generate(incident)
        self.repository.save(incident)
        self.publish(incident)
        log.info("incident_event", extra={"incident_id":incident.id, "event_type":event_type, "seq":len(incident.timeline)})

    def agent(self, incident: Incident, name: str, state: str, finding: str):
        agent = next(a for a in incident.agents if a.name == name)
        agent.state = state
        agent.finding = finding

    async def start(self, scenario_id: str, request: StartRequest) -> Incident:
        if scenario_id not in SCENARIOS:
            raise KeyError(scenario_id)
        async with self.lock:
            if self.task and not self.task.done():
                raise Conflict("An incident is already active. Reset it before starting another scenario.")
            scenario = SCENARIOS[scenario_id]
            incident = Incident(id=f"GM-{uuid4().hex[:12].upper()}", scenario_id=scenario_id, title=scenario.title,
                                source=scenario.source, mode=request.mode, auto_approve=request.auto_approve,
                                step_duration=request.step_duration or (1.7 if request.mode == "fast" else 5),
                                topology=build_topology(), agents=initial_agents(), telemetry=scenario_telemetry(scenario_id))
            self.current = incident
            self.resume_gate.set()
            self.skip_gate.clear()
            self.approval_gate.clear()
            asset(incident.topology, incident.source).state = SecurityState.COMPROMISED
            self.emit(incident, "INCIDENT_STARTED", f"{scenario.title}. Synthetic attack telemetry injected into the city twin.")
            self.task = asyncio.create_task(self.run(incident))
            return incident

    async def delay(self, incident: Incident, multiplier: float = 1):
        remaining = incident.step_duration * multiplier
        while remaining > 0:
            await self.resume_gate.wait()
            if self.skip_gate.is_set():
                self.skip_gate.clear()
                return
            started = time.monotonic()
            await asyncio.sleep(min(.025, remaining))
            if self.resume_gate.is_set():
                remaining -= time.monotonic()-started
        await self.resume_gate.wait()

    async def control(self, incident_id: str, command: str) -> Incident:
        async with self.lock:
            incident = self.get(incident_id)
            active = self.current is incident and self.task and not self.task.done()
            if command == "reset":
                if active:
                    self.task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self.task
                incident.status = "RESET"
                incident.phase = "READY"
                incident.topology = build_topology()
                if incident is self.current:
                    self.resume_gate.set()
                    self.approval_gate.set()
                    self.skip_gate.clear()
                self.emit(incident, "INCIDENT_RESET", "City twin reset. The incident record and reports remain in local history.")
                return incident
            if not active:
                raise Conflict("This incident is no longer running.")
            if command == "pause":
                if incident.status != "RUNNING":
                    raise Conflict("Only a running incident can be paused.")
                self.resume_gate.clear()
                incident.status = "PAUSED"
            elif command == "resume":
                if incident.status != "PAUSED":
                    raise Conflict("This incident is not paused.")
                incident.status = "RUNNING"
                self.resume_gate.set()
            elif command == "skip":
                if incident.status != "RUNNING":
                    raise Conflict("Skip requires a running incident and never bypasses approval.")
                self.skip_gate.set()
            else:
                raise KeyError(command)
            self.emit(incident, f"DEMO_{command.upper()}", f"Operator selected {command}.")
            return incident

    async def approve(self, incident_id: str, request: ApprovalRequest, actor: str = "OPERATOR") -> Incident:
        async with self.lock:
            incident = self.get(incident_id)
            if incident is not self.current or incident.status != "AWAITING_APPROVAL" or not incident.plan:
                raise Conflict("No approval is pending for this incident.")
            if request.plan_id != incident.plan.id or request.plan_version != incident.plan.version:
                raise Conflict("Approval refers to a stale response plan.")
            if self.approval_gate.is_set():
                raise Conflict("An approval decision has already been recorded.")
            incident.approvals.append(Approval(**request.model_dump(), actor=actor))
            self.emit(incident, "APPROVAL_RECORDED", f"{'Demo auto-approval' if actor == 'DEMO_AUTOMATION' else 'Operator'}: {request.decision.lower()} for plan v{request.plan_version}.", "Compliance")
            self.approval_gate.set()
            return incident

    async def approval(self, incident: Incident):
        assert incident.plan
        incident.status = "AWAITING_APPROVAL"
        incident.phase = "APPROVAL"
        self.agent(incident, "Compliance", "WAITING", "Shared-segment isolation requires approval. Safe fallback is available on rejection.")
        self.emit(incident, "APPROVAL_REQUIRED", "Approve shared edge-segment isolation, or reject to use endpoint-only containment.", "Compliance")
        if incident.auto_approve:
            try:
                await asyncio.wait_for(self.approval_gate.wait(), timeout=max(.05, incident.step_duration*1.2))
            except TimeoutError:
                try:
                    await self.approve(incident.id, ApprovalRequest(plan_id=incident.plan.id, plan_version=incident.plan.version, decision="APPROVE"), "DEMO_AUTOMATION")
                except Conflict:
                    # An operator may win the lock exactly as the timer expires.
                    # Their accepted decision takes precedence over demo automation.
                    if not self.approval_gate.is_set() or not any(a.plan_id == incident.plan.id and a.plan_version == incident.plan.version for a in incident.approvals):
                        raise
        else:
            await self.approval_gate.wait()
        decision = incident.approvals[-1]
        incident.status = "RUNNING"
        if decision.decision == "REJECT":
            incident.plan = ResponseAgent().plan(incident, fallback=True)
            incident.policy = ComplianceAgent().validate(incident, self.provider.simulated)
            incident.plan_history.append(incident.plan.model_copy(deep=True))
            incident.policy_history.append(PolicyReview(plan_id=incident.plan.id, plan_version=incident.plan.version, result=incident.policy.model_copy(deep=True)))
            self.agent(incident, "Response", "COMPLETE", f"Safe fallback v2 · {len(incident.plan.actions)} actions · shared-segment isolation removed")
            self.emit(incident, "SAFE_FALLBACK_SELECTED", "Rejected segment action removed. Version 2 protects services and quarantines only the source.", "Response")
        self.agent(incident, "Compliance", "COMPLETE", "Approval recorded; hard continuity policies remain enforced.")

    async def run(self, incident: Incident):
        try:
            await self.delay(incident)
            incident.phase = "DETECT"
            self.agent(incident, "Sentinel", "ANALYZING", "Inspecting synthetic flow and identity evidence.")
            detection = SentinelAgent().inspect(incident)
            self.emit(incident, "ANOMALY_DETECTED", detection.evidence[0], "Sentinel")
            await self.delay(incident)
            incident.classification = detection
            incident.phase = "CLASSIFY"
            technique = incident.classification.techniques[0]
            self.agent(incident, "Sentinel", "COMPLETE", f"{technique.id} · {technique.name} · {incident.classification.confidence:.0%} rule confidence")
            self.emit(incident, "THREAT_CLASSIFIED", incident.classification.reasoning, "Sentinel")
            self.agent(incident, "Impact", "ANALYZING", "Traversing enabled service dependencies and scoring each propagation path.")
            self.emit(incident, "IMPACT_ANALYSIS_STARTED", "Calculating downstream exposure from the compromised asset.", "Impact")
            await self.delay(incident)
            incident.impact = ImpactAgent().analyze(incident)
            incident.phase = "IMPACT"
            for risk in incident.impact.impacted:
                asset(incident.topology, risk.node_id).state = SecurityState.AT_RISK if risk.critical else SecurityState.WARNING
                for left, right in zip(risk.path, risk.path[1:]):
                    for edge in incident.topology.edges:
                        if edge.source == left and edge.target == right:
                            edge.state = "THREAT"
            self.agent(incident, "Impact", "COMPLETE", f"Risk {incident.impact.score}/100 · {len(incident.impact.critical_services)} critical services exposed")
            self.emit(incident, "IMPACT_ANALYSIS_COMPLETE", incident.impact.explanation, "Impact")
            self.agent(incident, "Response", "ANALYZING", "Comparing endpoint containment with broader segment isolation.")
            self.emit(incident, "RESPONSE_PLANNING", "Selecting a service-preserving containment strategy.", "Response")
            await self.delay(incident)
            incident.plan = ResponseAgent().plan(incident)
            incident.plan_history.append(incident.plan.model_copy(deep=True))
            incident.phase = "PLAN"
            self.agent(incident, "Response", "COMPLETE", f"{len(incident.plan.actions)} ordered actions · protect routes before isolation")
            self.emit(incident, "RESPONSE_PLAN_CREATED", incident.plan.rationale, "Response")
            self.agent(incident, "Compliance", "ANALYZING", "Dry-running the plan against critical-service continuity policies.")
            self.emit(incident, "POLICY_CHECK_STARTED", "Validating simulation scope, service routes and isolation boundaries.", "Compliance")
            await self.delay(incident)
            incident.policy = ComplianceAgent().validate(incident, self.provider.simulated)
            incident.policy_history.append(PolicyReview(plan_id=incident.plan.id, plan_version=incident.plan.version, result=incident.policy.model_copy(deep=True)))
            incident.phase = "POLICY"
            self.agent(incident, "Compliance", "COMPLETE", incident.policy.decision.replace("_", " "))
            self.emit(incident, "POLICY_CHECK_COMPLETE", " ".join(incident.policy.reasons), "Compliance")
            if incident.policy.decision == "REJECTED":
                raise ValueError("Response plan failed hard safety policy")
            if incident.policy.decision == "APPROVAL_REQUIRED":
                await self.approval(incident)
            check = ComplianceAgent().validate(incident, self.provider.simulated)
            if check.decision == "REJECTED":
                raise ValueError("Plan failed revalidation")
            if check.decision == "APPROVAL_REQUIRED" and not any(a.decision == "APPROVE" and a.plan_version == incident.plan.version for a in incident.approvals):
                raise ValueError("Plan lacks a matching approval")
            incident.phase = "NETWORK"
            self.agent(incident, "Network", "EXECUTING", "Applying simulated telecom capabilities in policy-approved order.")
            self.emit(incident, "NETWORK_RESPONSE_STARTED", "SIMULATED NETWORK-AS-CODE ACTIONS · local deterministic provider.", "Network")
            network = NetworkAgent(self.provider)
            for planned in incident.plan.actions:
                await self.resume_gate.wait()
                action = planned.model_copy(deep=True)
                action.status = "EXECUTING"
                incident.actions.append(action)
                self.emit(incident, "ACTION_EXECUTING", f"POST {action.endpoint} · {asset(incident.topology, action.target).name}", "Network")
                await self.delay(incident, .55)
                try:
                    action.result = await network.execute(action, incident)
                except Exception:
                    action.status = "FAILED"
                    raise
                await self.resume_gate.wait()
                if action.kind == "reroute":
                    protect(incident.topology, [action.target])
                elif action.kind == "qod":
                    asset(incident.topology, action.target).latency_ms = 8
                elif action.kind in ("quarantine", "isolate_segment"):
                    isolate(incident.topology, action.target)
                elif action.kind == "verify_location" and action.result.get("verification") == "FALSE":
                    action.result["trust"] = "RESTRICTED"
                action.status = "COMPLETE"
                action.executed_at = now()
                event_type = {"reroute":"TRAFFIC_REROUTED", "qod":"QOD_ACTIVATED", "quarantine":"DEVICE_ISOLATED", "isolate_segment":"SEGMENT_ISOLATED"}.get(action.kind, "CONTEXT_VERIFIED")
                self.emit(incident, event_type, action.result["summary"], "Network")
            incident.residual_impact = ImpactAgent().analyze(incident)
            if incident.residual_impact.score != 0 or not continuity_verified(incident.topology):
                raise ValueError("Containment or service continuity verification failed")
            for node in incident.topology.nodes:
                if node.state in (SecurityState.WARNING, SecurityState.AT_RISK):
                    node.state = SecurityState.ONLINE
            for edge in incident.topology.edges:
                if edge.state == "THREAT":
                    edge.state = "NORMAL"
            self.agent(incident, "Network", "COMPLETE", f"{len(incident.actions)} simulated actions completed · source isolated")
            incident.phase = "CONTAINED"
            incident.status = "CONTAINED"
            incident.ended_at = now()
            incident.outcome = "Source isolated; residual propagation risk 0/100; all six critical services remained online."
            self.emit(incident, "INCIDENT_CONTAINED", incident.outcome, "Network")
            self.agent(incident, "Report", "ANALYZING", "Building technical and executive reports from the incident evidence.")
            self.emit(incident, "REPORT_GENERATING", "Compiling evidence, approval history, actions and continuity measurements.", "Report")
            await self.delay(incident)
            self.agent(incident, "Report", "COMPLETE", "Executive and technical reports ready · evidence and timeline included")
            incident.phase = "COMPLETE"
            self.emit(incident, "REPORT_GENERATED", "Incident reports generated from actual state. Ready to review or export JSON.", "Report")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("simulation_failed", extra={"incident_id":incident.id})
            incident.status = "FAILED"
            incident.phase = "FAILED"
            incident.ended_at = now()
            incident.outcome = "Simulation stopped safely. Inspect local backend logs, then reset and rerun."
            self.emit(incident, "INCIDENT_FAILED", incident.outcome)

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            if self.current and self.current.status != "RESET":
                if self.current.status == "CONTAINED":
                    self.agent(self.current, "Report", "COMPLETE", "Report completed during orderly backend shutdown.")
                    self.current.phase = "COMPLETE"
                    self.emit(self.current, "REPORT_GENERATED", "Contained incident report finalized before backend shutdown.", "Report")
                else:
                    self.current.status = "INTERRUPTED"
                    self.emit(self.current, "ENGINE_STOPPED", "Backend stopped. Start a fresh run to restore deterministic execution.")
