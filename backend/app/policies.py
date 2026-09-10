from .models import Incident, Plan, PolicyDecision, SecurityState
from .topology import asset, protect, isolate, continuity_verified
from .provider import ENDPOINTS


def validate_plan(plan: Plan, incident: Incident, simulated: bool = True) -> PolicyDecision:
    """Dry-run the ordered plan against an independent copy before any execution."""
    rules = ["SIMULATION_ONLY", "NO_CRITICAL_ISOLATION", "PRESERVE_SERVICE_ROUTES", "APPROVE_SHARED_SEGMENT"]
    reasons: list[str] = []
    if not simulated:
        reasons.append("Only the local simulated provider is authorized.")
    twin = incident.topology.model_copy(deep=True)
    shared = False
    for action in plan.actions:
        if action.kind not in ENDPOINTS or action.endpoint != ENDPOINTS[action.kind]:
            reasons.append("Unknown or mismatched capability endpoint.")
            continue
        if action.target not in {n.id for n in twin.nodes}:
            reasons.append("Unknown target asset.")
            continue
        node = asset(twin, action.target)
        if action.kind == "reroute":
            protect(twin, [node.id])
        if action.kind in ("quarantine", "isolate_segment"):
            if node.critical:
                reasons.append(f"Cannot isolate critical service {node.name}.")
            if action.kind == "isolate_segment" or node.kind in ("gateway", "core", "edge"):
                shared = True
                affected = incident.impact.critical_services if incident.impact else []
                if any(asset(twin, n).state != SecurityState.PROTECTED for n in affected):
                    reasons.append("Protect every affected service before shared-segment isolation.")
            isolate(twin, node.id)
            if not continuity_verified(twin):
                reasons.append("Isolation would remove a critical service route.")
    if reasons:
        return PolicyDecision(decision="REJECTED", reasons=reasons, rules=rules)
    if shared:
        return PolicyDecision(decision="APPROVAL_REQUIRED", reasons=["Shared edge-segment isolation affects multiple tenants. Explicit approval is required; all critical service routes pass the safety dry-run."], rules=rules)
    return PolicyDecision(decision="APPROVED", reasons=["Endpoint containment is bounded. Protected routes preserve all six critical services."], rules=rules)
