"""Six logical agents exchange typed findings through the shared Incident."""
from .models import AgentState, Classification, Incident, Plan, Action
from .scenarios import SCENARIOS
from .risk import calculate_impact
from .policies import validate_plan
from .provider import ENDPOINTS, NetworkProvider
from .reporting import generate_report


def initial_agents() -> list[AgentState]:
    return [AgentState(name=n, role=r) for n, r in [
        ("Sentinel", "Detect & classify"), ("Impact", "Trace service exposure"),
        ("Response", "Plan safe containment"), ("Compliance", "Enforce operational policy"),
        ("Network", "Execute simulated capabilities"), ("Report", "Explain the outcome")]]


class SentinelAgent:
    def inspect(self, incident: Incident) -> Classification:
        observed = incident.telemetry
        matched = [key for key, matches in (
            ("camera", observed.remote_sessions > 5*observed.baseline_sessions and observed.exploit_signature),
            ("identity", observed.sim_swap_minutes_ago is not None and observed.sim_swap_minutes_ago <= 1440 and not observed.ownership_confirmed and not observed.location_matches),
            ("energy", observed.service_stop_requests >= 10 and not observed.maintenance_window),
        ) if matches]
        if len(matched) != 1:
            raise ValueError("Telemetry must match one explicit threat rule; normal or ambiguous observations are not classified.")
        scenario = SCENARIOS[matched[0]]
        evidence = list(scenario.evidence)
        if scenario.id == "camera":
            evidence[0] = f"Camera opened {observed.remote_sessions} unauthorized remote-service sessions in 10 seconds; baseline is {observed.baseline_sessions}."
        elif scenario.id == "identity":
            evidence[1] = f"SIM replacement occurred {observed.sim_swap_minutes_ago} minutes before the authentication anomaly."
        else:
            evidence[0] = f"Traffic controller sent {observed.service_stop_requests} unauthorized service-stop requests to the edge compute plane."
        return Classification(threat_type=scenario.threat_type, confidence=scenario.confidence, source=incident.source,
                              evidence=evidence, reasoning=scenario.explanation, techniques=[scenario.technique()])


class ImpactAgent:
    def analyze(self, incident: Incident):
        return calculate_impact(incident.topology, incident.source, SCENARIOS[incident.scenario_id].severity)


class ResponseAgent:
    def plan(self, incident: Incident, fallback: bool = False) -> Plan:
        steps: list[tuple[str, str, str, str]] = []
        add = lambda kind, target, reason, effect: steps.append((kind, target, reason, effect))
        add("verify_location", incident.source, "Verify the endpoint's network context.", "Establish location trust.")
        add("sim_swap", incident.source, "Correlate identity changes with detection evidence.", "Assess derived identity risk.")
        critical = incident.impact.critical_services if incident.impact else []
        for node_id in critical:
            add("reroute", node_id, "Keep this dependent service reachable before containment.", "Use protected core transport.")
        priority = [n for n in ("hospital", "emergency") if n in critical]
        if incident.scenario_id == "energy":
            priority = ["energy"]
        for node_id in priority:
            add("qod", node_id, "Reserve emergency connectivity during remediation.", "Simulated latency improves from 45 to 8 ms.")
        if SCENARIOS[incident.scenario_id].requires_approval and not fallback:
            add("isolate_segment", "edge", "Stop service-stop commands traversing the shared edge segment.", "Segment is isolated after dependent services reroute.")
        add("quarantine", incident.source, "Contain the source without shutting down dependent services.", "Disable all source threat paths.")
        version = 2 if fallback else 1
        return Plan(id=f"{incident.id}-plan", version=version,
                    strategy="Protect service routes, prioritize critical connectivity, then contain the source" + (" (safe operator-rejection fallback)" if fallback else ""),
                    rationale="Preserve critical service availability before changing endpoint or segment access. Context checks, service rerouting and containment are ordered and policy validated.",
                    actions=[Action(id=f"v{version}-{i+1:02}", kind=kind, target=target, endpoint=ENDPOINTS[kind], rationale=reason, expected_effect=effect)
                             for i, (kind, target, reason, effect) in enumerate(steps)])


class ComplianceAgent:
    def validate(self, incident: Incident, simulated: bool = True):
        assert incident.plan
        return validate_plan(incident.plan, incident, simulated)


class NetworkAgent:
    def __init__(self, provider: NetworkProvider):
        self.provider = provider

    async def execute(self, action: Action, incident: Incident):
        return await self.provider.execute(action, incident)


class ReportAgent:
    def generate(self, incident: Incident):
        return generate_report(incident)
