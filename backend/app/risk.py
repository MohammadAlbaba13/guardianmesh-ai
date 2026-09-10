from .models import AssetRisk, Impact, Topology, SecurityState
from .topology import asset


def risk_band(score: int) -> str:
    return "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MODERATE" if score >= 30 else "LOW"


def calculate_impact(twin: Topology, source: str, severity: float) -> Impact:
    """Maximum simple-path risk, excluding management/protected/disabled edges.

    score = 100 * severity * (.55*criticality + .25*exposure + .20/(1+.2*distance))
            * product(edge weights) * (1-protection).
    """
    start = asset(twin, source)
    if start.state in (SecurityState.ISOLATED, SecurityState.OFFLINE):
        return Impact(explanation="Source is isolated. No enabled risk path reaches a dependent service.")
    best: dict[str, AssetRisk] = {}
    outgoing = {n.id: [] for n in twin.nodes}
    for edge in twin.edges:
        if edge.enabled and edge.propagates_threat:
            outgoing[edge.source].append(edge)

    def visit(current: str, path: list[str], weight: float) -> None:
        for link in outgoing[current]:
            if link.target in path:
                continue
            node = asset(twin, link.target)
            if node.state in (SecurityState.ISOLATED, SecurityState.OFFLINE):
                continue
            route, distance = path + [node.id], len(path)
            path_weight = weight * link.weight
            proximity = 1 / (1 + .2 * distance)
            value = round(100 * severity * (.55*node.criticality + .25*node.exposure + .20*proximity)
                          * path_weight * (1-node.protection))
            score = min(100, max(0, value))
            risk = AssetRisk(node_id=node.id, score=score, distance=distance, path=route, critical=node.critical,
                             factors={"severity":severity, "criticality":node.criticality, "exposure":node.exposure,
                                      "proximity":proximity, "path_weight":path_weight, "protection":node.protection})
            if node.id not in best or score > best[node.id].score:
                best[node.id] = risk
            visit(node.id, route, path_weight)

    visit(source, [source], 1)
    impacted = sorted(best.values(), key=lambda r: (-r.score, r.node_id))
    critical = [r for r in impacted if r.critical and r.score > 0]
    worst = max(critical or impacted, key=lambda r: r.score, default=None)
    score = worst.score if worst else 0
    # Domain storytelling preferences only break equal scores; never alter risk.
    preferred = next((r for target in twin.preferred_targets for r in critical
                      if r.node_id == target and r.score == score), None)
    worst = preferred or worst
    return Impact(score=score, severity=risk_band(score), impacted=impacted,
                  critical_services=[r.node_id for r in critical], propagation_path=worst.path if worst else [],
                  explanation=f"{len(critical)} critical services are reachable through enabled dependency links. Peak risk {score}/100 combines asset criticality, exposure, graph distance, link trust and current protection.")
