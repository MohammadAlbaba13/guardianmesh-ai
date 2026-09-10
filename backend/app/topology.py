from .models import Asset, Link, Topology, SecurityState


def build_topology() -> Topology:
    specs = [
        ("camera", "IoT Security Camera", "camera", "hospital-zone", False, .45, .95, 0, 40),
        ("traffic", "Traffic Controller", "traffic", "city-zone", False, .7, .8, 0, 200),
        ("sensor", "Environmental Sensor", "sensor", "city-zone", False, .35, .75, 0, 360),
        ("telecom", "Telecom Edge Gateway", "gateway", "access-zone", False, .8, .7, 240, 40),
        ("edge", "Edge Compute Node", "edge", "energy-zone", False, .85, .6, 240, 280),
        ("core", "5G Core Network", "core", "core-zone", False, .95, .45, 480, 40),
        ("city", "City Network Gateway", "gateway", "city-zone", False, .9, .6, 710, 40),
        ("guardian", "GuardianMesh SOC", "guardian", "security-zone", False, 1, .1, 490, 340),
        ("hospital", "Hospital", "hospital", "hospital-zone", True, 1, .85, 950, 0),
        ("emergency", "Emergency Response", "emergency", "emergency-zone", True, 1, .8, 950, 135),
        ("energy", "Energy Grid", "energy", "energy-zone", True, 1, .8, 710, 290),
        ("traffic_center", "Traffic Management", "traffic", "city-zone", True, .9, .75, 950, 275),
        ("safety", "Public Safety Service", "safety", "city-zone", True, .95, .8, 950, 410),
        ("control", "Smart-City Control", "control", "city-zone", True, .95, .8, 710, 460),
    ]
    nodes = [Asset(id=a, name=b, kind=c, zone=d, critical=e, criticality=f, exposure=g, x=x, y=y)
             for a, b, c, d, e, f, g, x, y in specs]
    paths = [
        ("camera", "telecom", "data"), ("sensor", "telecom", "data"),
        ("traffic", "edge", "control"), ("telecom", "core", "identity"),
        ("core", "city", "data"), ("edge", "energy", "control"), ("edge", "control", "control"),
        *[("city", n.id, "data") for n in nodes if n.critical],
        ("guardian", "core", "management"), ("guardian", "edge", "management"),
    ]
    edges = [Link(id=f"{s}-{t}", source=s, target=t, kind=k, weight={"data":1, "control":.9, "identity":.95, "management":0}[k],
                  propagates_threat=k != "management", carries_service=k != "management") for s, t, k in paths]
    # Protected transport from the core bypasses potentially compromised access gateways.
    edges += [Link(id=f"protected-{n.id}", source="core", target=n.id, kind="protected", weight=.25,
                   propagates_threat=False, enabled=False) for n in nodes if n.critical]
    return Topology(nodes=nodes, edges=edges)


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
    """Each service must be operational and reachable from the healthy 5G core."""
    def healthy(node_id: str) -> bool:
        node = asset(twin, node_id)
        return node.operational and node.state not in (SecurityState.ISOLATED, SecurityState.OFFLINE)
    if not healthy("core"):
        return False
    reachable = {"core"}
    for _ in twin.nodes:
        for edge in twin.edges:
            if edge.enabled and edge.carries_service and edge.source in reachable:
                if healthy(edge.source) and healthy(edge.target):
                    reachable.add(edge.target)
    return all(healthy(n.id) and n.id in reachable for n in twin.nodes if n.critical)
