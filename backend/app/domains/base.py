"""Typed Domain Packs: evidence, response intent and outcome semantics for the core."""
from dataclasses import dataclass, field
from typing import Callable, Literal

from ..models import (Action, Classification, DomainMetadata, Incident, Metric, Plan,
                      Signal, SignalTelemetry, Technique, Telemetry, Topology)


@dataclass(frozen=True)
class SignalDefinition:
    id: str
    label: str
    kind: Literal["boolean", "integer", "number", "text"]
    unit: str = ""
    source: str = "synthetic fixture"
    minimum: float | None = None
    maximum: float | None = None

    def validate(self, value: object) -> None:
        valid = {"boolean": type(value) is bool, "integer": type(value) is int,
                 "number": type(value) in (int, float), "text": type(value) is str}[self.kind]
        if not valid:
            raise ValueError(f"Signal {self.id} must be {self.kind}.")
        if self.kind in ("integer", "number"):
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"Signal {self.id} is below its valid range.")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"Signal {self.id} is above its valid range.")


@dataclass(frozen=True)
class ResponsePolicy:
    context_capabilities: tuple[str, ...] = ("verify_location", "sim_swap")
    priority_targets: tuple[str, ...] = ()
    shared_target: str | None = None
    remediation: tuple[str, ...] = ("quarantine",)
    life_safety_first: bool = False
    strategy: str = "Protect dependent services, prioritize connectivity, and apply bounded remediation"
    rationale: str = "Preserve declared critical service routes before changing the affected endpoint context."


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    subtitle: str
    source: str
    severity: float
    threat_type: str
    confidence: float
    evidence: tuple[str, ...]
    technique_id: str = ""
    technique_name: str = ""
    tactic: str = ""
    explanation: str = ""
    domain: str = "Enterprise"
    requires_approval: bool = False
    category: str = "CYBER"
    signal_values: dict[str, bool | int | float | str] = field(default_factory=dict)
    response_policy: ResponsePolicy | None = None

    def technique(self) -> Technique:
        if not self.technique_id:
            raise ValueError("This scenario has an operational classification, not a MITRE technique.")
        return Technique(id=self.technique_id, name=self.technique_name, tactic=self.tactic,
                         domain=self.domain, explanation=self.explanation,
                         url=f"https://attack.mitre.org/techniques/{self.technique_id.replace('.', '/')}/")


@dataclass(frozen=True)
class DetectionRule:
    scenario_id: str
    matches: Callable[[Telemetry | SignalTelemetry], bool]
    evidence: Callable[[Telemetry | SignalTelemetry], list[str]]


@dataclass(frozen=True)
class DomainPack:
    metadata: DomainMetadata
    topology_factory: Callable[[], Topology]
    scenarios: dict[str, Scenario]
    permitted_capabilities: tuple[str, ...]
    detection_rules: tuple[DetectionRule, ...]
    response_policy: ResponsePolicy = field(default_factory=ResponsePolicy)
    signal_schema: tuple[SignalDefinition, ...] = ()
    legacy_telemetry: Callable[[str], Telemetry] | None = None
    extra_metrics: Callable[[Incident], list[Metric]] | None = None
    extra_verify: Callable[[Incident], list[str]] | None = None
    extra_policy: Callable[[Plan, Incident], list[str]] | None = None

    def topology(self) -> Topology:
        return self.topology_factory()

    def catalog(self) -> list[dict]:
        return [{"id": s.id, "domain_id": self.metadata.id, "title": s.title,
                 "subtitle": s.subtitle, "source": s.source, "category": s.category,
                 "requires_approval": s.requires_approval} for s in self.scenarios.values()]

    def telemetry(self, scenario_id: str) -> Telemetry | SignalTelemetry:
        scenario = self.scenarios[scenario_id]
        if self.legacy_telemetry:
            return self.legacy_telemetry(scenario_id)
        values = scenario.signal_values
        result = SignalTelemetry(signals=[Signal(id=s.id, value=values[s.id], unit=s.unit,
                                                 source=s.source) for s in self.signal_schema])
        self.validate_telemetry(result)
        return result

    def validate_telemetry(self, telemetry: Telemetry | SignalTelemetry) -> None:
        if self.legacy_telemetry:
            if not isinstance(telemetry, Telemetry):
                raise ValueError("Smart City requires its validated legacy telemetry model.")
            return
        if not isinstance(telemetry, SignalTelemetry):
            raise ValueError("This Domain Pack requires typed signal telemetry.")
        observations = {signal.id: signal.value for signal in telemetry.signals}
        expected = {definition.id for definition in self.signal_schema}
        if len(observations) != len(telemetry.signals) or set(observations) != expected:
            raise ValueError("Telemetry must contain each declared domain signal exactly once.")
        for definition in self.signal_schema:
            definition.validate(observations[definition.id])

    def inspect(self, incident: Incident) -> Classification:
        self.validate_telemetry(incident.telemetry)
        matched = [rule for rule in self.detection_rules if rule.matches(incident.telemetry)]
        if len(matched) != 1:
            raise ValueError("Telemetry must match one explicit threat rule; normal or ambiguous observations are not classified.")
        rule = matched[0]
        scenario = self.scenarios[rule.scenario_id]
        return Classification(threat_type=scenario.threat_type, confidence=scenario.confidence,
                              source=incident.source, evidence=rule.evidence(incident.telemetry),
                              reasoning=scenario.explanation,
                              techniques=[scenario.technique()] if scenario.technique_id else [])

    def assess_context(self, incident: Incident) -> None:
        """Derive declared trust requirements from observed signals, never a domain id.

        The score is a deterministic triage index, not verified identity or a
        probability. Restriction may lower trust further; step-up stays pending.
        """
        if not isinstance(incident.telemetry, SignalTelemetry):
            return
        from ..topology import asset
        observations = {signal.id: signal.value for signal in incident.telemetry.signals}
        deductions = 0
        if "sim_swap_minutes_ago" in observations and observations["sim_swap_minutes_ago"] <= 1440:
            deductions += 25
        deductions += 15 if observations.get("device_changed") is True else 0
        for key in ("location_matches", "number_verified", "ownership_confirmed"):
            deductions += 20 if observations.get(key) is False else 0
        if incident.source in incident.topology.required_trust:
            asset(incident.topology, incident.source).trust_score = max(0, 100-deductions)

    def plan(self, incident: Incident, fallback: bool = False) -> Plan:
        from ..capabilities.registry import capability
        scenario = self.scenarios[incident.scenario_id]
        policy = scenario.response_policy or self.response_policy
        steps: list[tuple[str, str, str, str]] = []
        for kind in policy.context_capabilities:
            steps.append((kind, incident.source, "Correlate this network signal with supplied domain evidence.",
                          "Record an explicitly simulated context result."))
        critical = incident.impact.critical_services if incident.impact else []
        if policy.life_safety_first:
            priority = {node.id: node.priority for node in incident.topology.nodes}
            critical = sorted(critical, key=lambda target: priority[target])
        for target in critical:
            steps.append(("reroute", target, "Preserve this dependency before remediation.",
                          "Enable the domain's declared protected service route."))
        for target in policy.priority_targets:
            if target in critical:
                steps.append(("qod", target, "Prioritize this domain's essential application flow.",
                              "Apply the local simulator's 8 ms QoD profile; no carrier guarantee."))
        if scenario.requires_approval and policy.shared_target and not fallback:
            steps.append(("isolate_segment", policy.shared_target,
                          "Contain shared infrastructure only after dependent routes are protected and approval is recorded.",
                          "Isolate the declared shared segment in the digital twin."))
        effects = {"quarantine": "Disable the affected endpoint's routes in the simulation.",
                   "restrict_session": "Restrict this session's trust and block its propagation without disabling shared services.",
                   "step_up": "Mark additional verification as required; do not claim identity has been verified.",
                   "stabilize": "Relieve modeled source congestion while retaining sensor and emergency availability."}
        for kind in policy.remediation:
            steps.append((kind, incident.source, "Apply bounded remediation to the affected context only.", effects[kind]))
        version = 2 if fallback else 1
        return Plan(id=f"{incident.id}-plan", version=version,
                    strategy=policy.strategy + (" (safe operator-rejection fallback)" if fallback else ""),
                    rationale=policy.rationale,
                    actions=[Action(id=f"v{version}-{i+1:02}", kind=kind, target=target,
                                    endpoint=capability(kind).endpoint, rationale=reason, expected_effect=effect)
                             for i, (kind, target, reason, effect) in enumerate(steps)])

    def metrics(self, incident: Incident) -> list[Metric]:
        from ..topology import online_services
        impact = incident.residual_impact or incident.impact
        services = [node for node in incident.topology.nodes if node.critical]
        result = [Metric(id="services_online", label=self.metadata.services_label,
                         value=online_services(incident.topology), unit=f"/ {len(services)}", direction="higher",
                         description="Declared services that remain operational in this simulated topology."),
                  Metric(id="residual_risk", label=self.metadata.risk_label, value=impact.score if impact else 0,
                         unit="/ 100", direction="lower", description="Calculated graph exposure index; not a probability."),
                  Metric(id="critical_latency", label="Essential flow latency",
                         value=round(sum(n.latency_ms for n in services)/max(1,len(services)), 1), unit="ms",
                         direction="lower", description="Mean simulated latency across declared essential services.")]
        return result + (self.extra_metrics(incident) if self.extra_metrics else [])

    def verify(self, incident: Incident) -> list[str]:
        from ..topology import asset, continuity_verified
        errors = []
        if not continuity_verified(incident.topology):
            errors.append("Declared critical service connectivity did not survive remediation.")
        for node_id in incident.topology.required_trust:
            node = asset(incident.topology, node_id)
            if node.trust_score < 70 and not (node.session_restricted and node.verification_required):
                errors.append(f"Low-trust context {node_id} lacks both session restriction and pending step-up verification.")
        if incident.residual_impact is None:
            errors.append("Residual impact has not been calculated.")
        elif incident.residual_impact.score != 0:
            errors.append("A residual propagation path remains after remediation.")
        policy = self.scenarios[incident.scenario_id].response_policy or self.response_policy
        source = asset(incident.topology, incident.source)
        if "quarantine" in policy.remediation and source.state != "ISOLATED":
            errors.append("Affected source was not isolated.")
        if "restrict_session" in policy.remediation and not source.session_restricted:
            errors.append("Affected session was not restricted.")
        if "step_up" in policy.remediation and not source.verification_required:
            errors.append("Required step-up verification was not recorded.")
        if "stabilize" in policy.remediation and (not source.operational or source.state != "PROTECTED"):
            errors.append("Environmental source was not stabilized while remaining operational.")
        return errors + (self.extra_verify(incident) if self.extra_verify else [])

    def policy_errors(self, plan: Plan, incident: Incident) -> list[str]:
        errors = []
        if any(action.kind not in self.permitted_capabilities for action in plan.actions):
            errors.append("The plan invokes a capability outside this Domain Pack's allowlist.")
        policy = self.scenarios[incident.scenario_id].response_policy or self.response_policy
        for action in plan.actions:
            if action.kind in ("restrict_session", "step_up", "stabilize") and action.target != incident.source:
                errors.append("Trust or stabilization actions must remain bounded to the affected source context.")
            if "restrict_session" in policy.remediation and action.kind in ("quarantine", "isolate_segment"):
                errors.append("A single suspicious user cannot justify shutting down shared domain infrastructure.")
            if "stabilize" in policy.remediation and action.kind in ("quarantine", "isolate_segment"):
                errors.append("Environmental response must preserve sensor ingestion and emergency communications.")
        return errors + (self.extra_policy(plan, incident) if self.extra_policy else [])


def trust_metrics(incident: Incident) -> list[Metric]:
    from ..topology import asset
    source = asset(incident.topology, incident.source)
    return [Metric(id="session_trust", label="Affected session trust", value=source.trust_score, unit="/ 100",
                   direction="neutral", description="Triage index: recent SIM -25, changed device -15, inconsistent location/number/ownership -20 each. Bounded restriction caps trust at 20; pending verification never proves identity."),
            Metric(id="verification_required", label="Step-up required", value=int(source.verification_required),
                   unit="", direction="neutral", description="One means operator/user verification remains required.")]


def topology_from_specs(specs: list[tuple], edges: list[tuple[str, str, str]], *, roots: list[str],
                        priorities: list[str], shared: tuple[str, ...] = (), trusted: tuple[str, ...] = ()) -> Topology:
    """Build explicitly authored graphs; each pack provides its own dependency structure."""
    from ..models import Asset, Link
    nodes = [Asset(id=i, name=name, kind=kind, zone=zone, critical=critical, criticality=importance,
                   exposure=exposure, x=x, y=y, priority=1 if i in priorities else 3, shared=i in shared)
             for i,name,kind,zone,critical,importance,exposure,x,y in specs]
    links = [Link(id=f"{s}-{t}", source=s, target=t, kind=kind,
                  weight=.95 if kind=="identity" else .9 if kind=="control" else 1,
                  propagates_threat=kind!="management", carries_service=kind!="management")
             for s,t,kind in edges]
    links += [Link(id=f"protected-{node.id}", source=roots[0], target=node.id, kind="protected",
                   weight=.25, propagates_threat=False, enabled=False) for node in nodes if node.critical]
    return Topology(nodes=nodes, edges=links, service_roots=roots, preferred_targets=priorities,
                    required_trust=list(trusted))
