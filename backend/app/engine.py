import asyncio
import contextlib
import logging
import time
import os
from uuid import uuid4
from .models import Incident, StartRequest, ApprovalRequest, Approval, PolicyReview, TimelineEvent, ServiceSample, SecurityState, now
from .domains.registry import get_domain
from .topology import asset, online_services, apply_action_effect, continuity_verified
from .agents import initial_agents, SentinelAgent, ImpactAgent, ResponseAgent, ComplianceAgent, NetworkAgent, ReportAgent
from .providers import select_provider
from .providers.service import NetworkActionService
from .providers.qod import NetworkError
from .intelligence import choose_reasoner
from .capabilities.registry import get_capability
from .persistence import Repository

log = logging.getLogger("guardianmesh.engine")


class Conflict(Exception):
    pass


class SimulationEngine:
    def __init__(self, repository: Repository, provider=None, reasoner=None):
        self.repository = repository
        self._custom_provider = provider is not None
        self.provider = provider or select_provider()
        self.reasoner = reasoner or choose_reasoner()
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
        incident.metrics = get_domain(incident.domain_id).metrics(incident)
        incident.samples.append(ServiceSample(step=len(incident.timeline), online=online_services(incident.topology), risk=risk,
                                             latency=round(sum(n.latency_ms for n in critical)/max(1, len(critical))),
                                             total=len(critical), metrics=[m.model_copy(deep=True) for m in incident.metrics]))
        if event_type == "REPORT_GENERATED":
            incident.report = ReportAgent().generate(incident)
        self.repository.save(incident)
        self.publish(incident)
        log.info("incident_event", extra={"incident_id":incident.id, "event_type":event_type, "seq":len(incident.timeline)})

    def agent(self, incident: Incident, name: str, state: str, finding: str):
        agent = next(a for a in incident.agents if a.name == name)
        agent.state = state
        agent.finding = finding

    async def start(self, scenario_id: str, request: StartRequest, domain_id: str = "smart_city") -> Incident:
        pack = get_domain(domain_id)
        if scenario_id not in pack.scenarios:
            raise KeyError(scenario_id)
        async with self.lock:
            if self.task and not self.task.done():
                raise Conflict("An incident is already active. Reset it before starting another scenario.")
            if not self._custom_provider:
                self.provider = select_provider(request.execution_mode, request.allow_fallback)
            if request.ai_mode is not None:
                self.reasoner = choose_reasoner(request.ai_mode)
            if isinstance(self.provider, NetworkActionService):
                self.provider.checkpoint = self.emit
            scenario = pack.scenarios[scenario_id]
            incident = Incident(id=f"GM-{uuid4().hex[:12].upper()}", scenario_id=scenario_id, title=scenario.title,
                                domain_id=domain_id, domain=pack.metadata, category=scenario.category,
                                execution_mode=request.execution_mode or os.getenv("GUARDIANMESH_NETWORK_MODE", "SIMULATION").upper(),
                                allow_fallback=request.allow_fallback, manual_approval=request.manual_approval,
                                severity_override={"LOW":.3,"MEDIUM":.5,"HIGH":.75,"CRITICAL":1}.get(request.severity),
                                provider_name=getattr(self.provider, "name", type(self.provider).__name__), provider_mode=getattr(self.provider, "mode", "SIMULATED"),
                                provider_notice=getattr(self.provider, "notice", None),
                                source=scenario.source, mode=request.mode, auto_approve=request.auto_approve,
                                step_duration=request.step_duration or (1.7 if request.mode == "fast" else 5),
                                topology=pack.topology(), agents=initial_agents(), telemetry=pack.telemetry(scenario_id))
            # Persist the effective setting so clients never advertise automation
            # while the backend is waiting for a real operator decision.
            incident.auto_approve = request.auto_approve and incident.execution_mode == "SIMULATION" and not incident.manual_approval
            self.current = incident
            self.resume_gate.set()
            self.skip_gate.clear()
            self.approval_gate.clear()
            asset(incident.topology, incident.source).state = SecurityState.COMPROMISED if incident.category == "CYBER" else SecurityState.WARNING
            incident.metrics_before = pack.metrics(incident)
            self.emit(incident, "INCIDENT_STARTED", f"{scenario.title}. Synthetic {incident.category.lower()} evidence loaded into the {pack.metadata.name} twin.")
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
                if active and any(a.status == "EXECUTING" and a.result.get("execution_state") in ("SENDING", "ACCEPTED") for a in incident.actions):
                    raise Conflict("Network request in flight. Wait for its bounded completion before resetting.")
                if active:
                    self.task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self.task
                if any(a.result.get("external_session_id") and a.result.get("cleanup") != "DELETED" for a in incident.actions):
                    manager = self.provider if isinstance(self.provider, NetworkActionService) else NetworkActionService("LIVE")
                    manager.checkpoint = self.emit
                    try:
                        await manager.cleanup(incident)
                        if incident.report:
                            incident.report = ReportAgent().generate(incident)
                    except NetworkError as exc: raise Conflict("QoD cleanup failed: " + exc.code + ". Retry Reset; evidence retained.") from None
                incident.status = "RESET"
                incident.phase = "READY"
                incident.topology = get_domain(incident.domain_id).topology()
                if incident is self.current:
                    self.resume_gate.set()
                    self.approval_gate.set()
                    self.skip_gate.clear()
                self.emit(incident, "INCIDENT_RESET", "Domain twin reset. The incident record and reports remain in local history.")
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
        self.agent(incident, "Compliance", "WAITING", "Review the validated plan before provider execution. No network calls have been sent.")
        self.emit(incident, "APPROVAL_REQUIRED", "Approve the policy-validated response plan. Rejection prevents the proposed execution.", "Compliance")
        if incident.auto_approve and incident.execution_mode == "SIMULATION" and not incident.manual_approval:
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
            if incident.manual_approval or incident.execution_mode != "SIMULATION":
                self.emit(incident, "ACTION_REJECTED", "Operator rejected this plan. No network action executed.", "Compliance")
                raise NetworkError("APPROVAL_REJECTED")
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
            label = " · ".join(f"{t.id} {t.name}" for t in incident.classification.techniques) or incident.classification.threat_type
            self.agent(incident, "Sentinel", "COMPLETE", f"{label} · {incident.classification.confidence:.0%} rule confidence")
            self.emit(incident, "THREAT_CLASSIFIED", incident.classification.reasoning, "Sentinel")
            self.agent(incident, "Impact", "ANALYZING", "Traversing enabled service dependencies and scoring each propagation path.")
            self.emit(incident, "IMPACT_ANALYSIS_STARTED", "Calculating downstream exposure from the compromised asset.", "Impact")
            await self.delay(incident)
            incident.impact = ImpactAgent().analyze(incident)
            get_domain(incident.domain_id).assess_context(incident)
            incident.metrics_before = get_domain(incident.domain_id).metrics(incident)
            incident.phase = "IMPACT"
            for risk in incident.impact.impacted:
                asset(incident.topology, risk.node_id).state = SecurityState.AT_RISK if risk.critical else SecurityState.WARNING
                for left, right in zip(risk.path, risk.path[1:]):
                    for edge in incident.topology.edges:
                        if edge.source == left and edge.target == right:
                            edge.state = "THREAT"
            self.agent(incident, "Impact", "COMPLETE", f"Risk {incident.impact.score}/100 · {len(incident.impact.critical_services)} critical services exposed")
            self.emit(incident, "IMPACT_ANALYSIS_COMPLETE", incident.impact.explanation, "Impact")
            self.emit(incident, "REASONING_STARTED", "Advisory reasoning started; deterministic policy retains execution authority.", "Response")
            incident.reasoning = await self.reasoner.reason(incident, list(get_domain(incident.domain_id).permitted_capabilities))
            incident.reasoner_mode = incident.reasoning.mode
            self.emit(incident, "REASONING_COMPLETE", incident.reasoning.interpretation +
                      (f" Deterministic fallback: {incident.reasoning.fallback_reason}" if incident.reasoning.fallback_reason else ""), "Response")
            self.agent(incident, "Response", "ANALYZING", "Comparing endpoint containment with broader segment isolation.")
            self.emit(incident, "RESPONSE_PLANNING", "Selecting a service-preserving containment strategy.", "Response")
            await self.delay(incident)
            incident.plan = ResponseAgent().plan(incident)
            incident.plan_history.append(incident.plan.model_copy(deep=True))
            incident.phase = "PLAN"
            self.agent(incident, "Response", "COMPLETE", f"{len(incident.plan.actions)} ordered actions · protect routes before isolation")
            self.emit(incident, "RESPONSE_PLAN_CREATED", incident.plan.rationale, "Response")
            self.agent(incident, "Compliance", "ANALYZING", "Dry-running the plan against critical-service continuity policies.")
            self.emit(incident, "POLICY_CHECK_STARTED", "Validating capability scope, service routes and isolation boundaries.", "Compliance")
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
            self.agent(incident, "Network", "EXECUTING", "Applying capabilities in policy-approved order; each result records its execution provenance.")
            self.emit(incident, "NETWORK_RESPONSE_STARTED", f"{incident.execution_mode} requested. {self.provider.name if hasattr(self.provider, 'name') else 'Configured provider'}. Twin controls remain simulated.", "Network")
            network = NetworkAgent(self.provider)
            for planned in incident.plan.actions:
                await self.resume_gate.wait()
                action = planned.model_copy(deep=True)
                action.status = "EXECUTING"
                incident.actions.append(action)
                self.emit(incident, "ACTION_EXECUTING", f"{get_capability(action.kind).name} · {asset(incident.topology, action.target).name}", "Network")
                await self.delay(incident, .55)
                try:
                    action.result = await network.execute(action, incident)
                except Exception:
                    action.status = "FAILED"
                    self.emit(incident, "ACTION_FAILED", action.result.get("summary", "Provider execution failed safely."), "Network")
                    raise
                await self.resume_gate.wait()
                is_sim = action.result.get("simulated") is True and action.result.get("mode") == "SIMULATED"
                is_live = (isinstance(self.provider, NetworkActionService) and action.kind == "qod"
                           and action.result.get("mode") == "LIVE" and action.result.get("simulated") is False
                           and action.result.get("verification") == "VERIFIED" and action.result.get("external_session_id"))
                if not (is_sim or is_live):
                    action.status = "FAILED"
                    raise ValueError("Provider result lacks authorized execution evidence")
                if is_live:
                    incident.provider_mode = "LIVE"
                apply_action_effect(action, incident.topology)
                if action.kind == "verify_location" and action.result.get("verification") == "FALSE":
                    action.result["trust"] = "RESTRICTED"
                action.status = "COMPLETE"
                action.executed_at = now()
                event_type = {"reroute":"TRAFFIC_REROUTED", "qod":"QOD_ACTIVATED", "quarantine":"DEVICE_ISOLATED", "isolate_segment":"SEGMENT_ISOLATED"}.get(action.kind, "CONTEXT_VERIFIED")
                self.emit(incident, event_type, action.result["summary"], "Network")
            incident.residual_impact = ImpactAgent().analyze(incident)
            errors = get_domain(incident.domain_id).verify(incident)
            if not continuity_verified(incident.topology):
                errors.append("Required service connectivity verification failed")
            if errors:
                raise ValueError("; ".join(errors))
            for node in incident.topology.nodes:
                if node.state in (SecurityState.WARNING, SecurityState.AT_RISK):
                    node.state = SecurityState.ONLINE
            for edge in incident.topology.edges:
                if edge.state == "THREAT":
                    edge.state = "NORMAL"
            self.agent(incident, "Network", "COMPLETE", f"{len(incident.actions)} evidenced actions completed · digital twin verification passed")
            incident.phase = "CONTAINED"
            incident.status = "CONTAINED"
            incident.ended_at = now()
            source = asset(incident.topology, incident.source)
            total = sum(n.critical for n in incident.topology.nodes)
            source_result = "Source isolated" if source.state == SecurityState.ISOLATED else "Affected session restricted; step-up verification required" if source.session_restricted else "Connectivity stabilized; source remains operational"
            incident.outcome = f"{source_result}; residual dependency risk {incident.residual_impact.score}/100; {online_services(incident.topology)}/{total} required services online."
            self.emit(incident, "INCIDENT_CONTAINED", incident.outcome, "Network")
            self.agent(incident, "Report", "ANALYZING", "Building technical and executive reports from the incident evidence.")
            self.emit(incident, "REPORT_GENERATING", "Compiling evidence, approval history, actions and continuity measurements.", "Report")
            await self.delay(incident)
            self.agent(incident, "Report", "COMPLETE", "Executive and technical reports ready · evidence and timeline included")
            incident.phase = "COMPLETE"
            self.emit(incident, "REPORT_GENERATED", "Incident reports generated from actual state. Ready to review or export JSON.", "Report")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("incident_execution_failed", extra={"incident_id":incident.id})
            incident.status = "FAILED"
            incident.phase = "FAILED"
            incident.ended_at = now()
            incident.outcome = ("Execution stopped safely: " + exc.code) if isinstance(exc, NetworkError) else "Execution stopped safely; deterministic validation failed."
            self.emit(incident, "INCIDENT_FAILED", incident.outcome)
            incident.report = ReportAgent().generate(incident)
            self.repository.save(incident)
            self.publish(incident)

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
