"""Six logical agents exchange typed findings through the shared Incident."""
from .models import AgentState, Classification, Incident, Plan, Action
from .domains.registry import get_domain
from .risk import calculate_impact
from .policies import validate_plan
from .provider import NetworkProvider
from .reporting import generate_report


def initial_agents() -> list[AgentState]:
    return [AgentState(name=n, role=r) for n, r in [
        ("Sentinel", "Detect & classify"), ("Impact", "Trace service exposure"),
        ("Response", "Plan safe containment"), ("Compliance", "Enforce operational policy"),
        ("Network", "Execute simulated capabilities"), ("Report", "Explain the outcome")]]


class SentinelAgent:
    def inspect(self, incident: Incident) -> Classification:
        return get_domain(incident.domain_id).inspect(incident)


class ImpactAgent:
    def analyze(self, incident: Incident):
        pack = get_domain(incident.domain_id)
        return calculate_impact(incident.topology, incident.source, pack.scenarios[incident.scenario_id].severity)


class ResponseAgent:
    def plan(self, incident: Incident, fallback: bool = False) -> Plan:
        return get_domain(incident.domain_id).plan(incident, fallback=fallback)


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
