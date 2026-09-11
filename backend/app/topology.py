from .models import Asset, Link, Topology, SecurityState


def build_topology() -> Topology:
    """Compatibility entry point for the original Smart City catalog."""
    from .domains.smart_city import build_topology as smart_city_topology
    return smart_city_topology()


def asset(twin: Topology, node_id: str) -> Asset:
    return next(n for n in twin.nodes if n.id == node_id)


def online_services(twin: Topology) -> int:
    return sum(n.critical and n.operational for n in twin.nodes)


def isolate(twin: Topology, target: str) -> None:
    node = asset(twin, target)
    node.state = SecurityState.ISOLATED
    for edge in twin.edges:
        if target in (edge.source, edge.target) and edge.kind != "management":
            edge.enabled = False
            edge.state = "BLOCKED"


def protect(twin: Topology, targets: list[str]) -> None:
    for node_id in targets:
        node = asset(twin, node_id)
        node.state = SecurityState.PROTECTED
        node.protection = .95
        for edge in twin.edges:
            if edge.id == f"protected-{node_id}":
                edge.enabled = True
                edge.state = "PROTECTED"


def continuity_verified(twin: Topology) -> bool:
    """Verify each declared critical service from the domain's healthy roots."""
    def healthy(node_id: str) -> bool:
        node = asset(twin, node_id)
        return node.operational and node.state not in (SecurityState.ISOLATED, SecurityState.OFFLINE)
    if not twin.service_roots or not all(healthy(root) for root in twin.service_roots):
        return False
    reachable = set(twin.service_roots)
    for _ in twin.nodes:
        for edge in twin.edges:
            if edge.enabled and edge.carries_service and edge.source in reachable:
                if healthy(edge.source) and healthy(edge.target):
                    reachable.add(edge.target)
    return all(healthy(n.id) and n.id in reachable for n in twin.nodes if n.critical)


def apply_action_effect(action, twin: Topology) -> None:
    """Apply a completed simulated capability to the twin; also used for dry-runs.

    Trust restrictions bound one session's risk propagation without disabling its
    service connectivity. Stabilization models congestion relief, not weather
    removal or sensor quarantine. Every residual score is recomputed afterward.
    """
    node = asset(twin, action.target)
    if action.kind == "reroute":
        protect(twin, [node.id])
    elif action.kind == "qod":
        if action.result.get("simulated", True):
            node.latency_ms = int(action.result.get("latency_after_ms", 8))
    elif action.kind in ("quarantine", "isolate_segment"):
        isolate(twin, node.id)
    elif action.kind == "restrict_session":
        node.session_restricted = True
        node.trust_score = 20
        node.state = SecurityState.PROTECTED
        for edge in twin.edges:
            if edge.source == node.id and edge.propagates_threat:
                edge.propagates_threat = False
                edge.state = "PROTECTED"
    elif action.kind == "step_up":
        node.verification_required = True
    elif action.kind == "stabilize":
        node.state = SecurityState.PROTECTED
        node.protection = .95
        for edge in twin.edges:
            if edge.source == node.id and edge.propagates_threat:
                edge.propagates_threat = False
                edge.state = "PROTECTED"
