"""Universal invariants plus a pack's domain-specific policy, before execution."""
from .models import Incident, Plan, PolicyDecision, SecurityState
from .topology import asset, apply_action_effect, continuity_verified
from .capabilities.registry import get_capability
from .domains.registry import get_domain


def validate_plan(plan: Plan, incident: Incident, simulated: bool = True) -> PolicyDecision:
    rules = ["SIMULATION_ONLY", "VALID_TARGET_AND_CAPABILITY", "NO_CRITICAL_ISOLATION",
             "PRESERVE_SERVICE_ROUTES", "APPROVE_SHARED_SEGMENT", "DOMAIN_POLICY"]
    if incident.execution_mode != "SIMULATION":
        rules[0] = "BOUND_QOD_ONLY_EXTERNAL"
    pack = get_domain(incident.domain_id)
    reasons: list[str] = []
    if not simulated and incident.execution_mode == "SIMULATION":
        reasons.append("Only the local simulated provider is authorized for execution.")
    if not plan.actions or len({a.id for a in plan.actions}) != len(plan.actions):
        reasons.append("Plans need uniquely identified actions.")
    reasons.extend(pack.policy_errors(plan, incident))
    twin = incident.topology.model_copy(deep=True)
    shared = False
    for action in plan.actions:
        try:
            capability = get_capability(action.kind)
        except (KeyError, ValueError):
            reasons.append("Unknown capability.")
            continue
        if action.kind not in pack.permitted_capabilities or action.endpoint != capability.endpoint:
            reasons.append("Unsupported domain capability or mismatched internal operation label.")
            continue
        if action.target not in {n.id for n in twin.nodes}:
            reasons.append("Unknown target asset.")
            continue
        node = asset(twin, action.target)
        if action.kind in ("reroute", "qod") and not node.critical:
            reasons.append("Service protection and priority must target a declared critical service.")
        if action.kind == "reroute" and not any(e.kind == "protected" and e.target == node.id
                                                and e.source in twin.service_roots for e in twin.edges):
            reasons.append("The topology has no declared protected route for this service.")
        if action.kind in ("restrict_session", "step_up", "stabilize") and (node.critical or node.id != incident.source):
            reasons.append("Bounded trust and stabilization controls must target the affected source context.")
        if action.kind in ("quarantine", "isolate_segment"):
            if node.critical:
                reasons.append(f"Cannot isolate critical service {node.name}.")
            if action.kind == "isolate_segment" or node.shared:
                shared = True
                affected = incident.impact.critical_services if incident.impact else []
                if any(asset(twin, n).state != SecurityState.PROTECTED for n in affected):
                    reasons.append("Protect every affected service before shared-segment isolation.")
        apply_action_effect(action, twin)
        if not continuity_verified(twin):
            reasons.append("Action would remove a required critical service route.")
    if reasons:
        return PolicyDecision(decision="REJECTED", reasons=list(dict.fromkeys(reasons)), rules=rules)
    if shared or incident.manual_approval or incident.execution_mode != "SIMULATION":
        return PolicyDecision(decision="APPROVAL_REQUIRED", reasons=[
            "Explicit approval is required for this plan. All required service routes pass the safety dry-run."
        ], rules=rules)
    total = sum(n.critical for n in twin.nodes)
    return PolicyDecision(decision="APPROVED", reasons=[
        f"Actions are bounded to the allowed domain scope. Protected routes preserve all {total} required services."
    ], rules=rules)
