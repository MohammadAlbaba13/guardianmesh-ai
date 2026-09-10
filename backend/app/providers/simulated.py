"""Deterministic evidence; topology mutation remains policy-governed in core."""
from copy import deepcopy
from collections import deque
from typing import Any
from ..capabilities import get_capability
from ..models import Action, Incident, SignalTelemetry, SecurityState
from .base import CapabilityResult


class SimulatedNetworkProvider:
    name = "Local deterministic Network-as-Code simulator"
    mode = "SIMULATED"
    simulated = True

    def __init__(self, requested_mode: str = "simulated", notice: str | None = None):
        self.requested_mode = requested_mode
        self.notice = notice
        self._completed: dict[tuple[str, str], tuple[tuple[str, str, str], dict[str, Any]]] = {}

    async def execute(self, action: Action, incident: Incident) -> dict[str, Any]:
        operation = get_capability(action.kind)
        if action.endpoint != operation.endpoint:
            raise ValueError("Capability endpoint label does not match the registry")
        node = next((n for n in incident.topology.nodes if n.id == action.target), None)
        if node is None:
            raise ValueError("Capability target does not exist")
        if action.kind in ("quarantine", "isolate_segment", "restrict_session") and node.critical:
            raise ValueError("Critical-service isolation or session restriction is forbidden")
        key = (incident.id, action.id)
        signature = (action.kind, action.target, action.endpoint)
        if key in self._completed:
            previous, result = self._completed[key]
            if signature != previous:
                raise ValueError("Idempotency key reused with different capability arguments")
            return deepcopy(result)

        telemetry = incident.telemetry
        def signal(name: str, default=None):
            return telemetry.get(name, default) if isinstance(telemetry, SignalTelemetry) else getattr(telemetry, name, default)

        minutes = signal("sim_swap_minutes_ago")
        swapped = minutes is not None and minutes <= 1440
        matches = signal("location_matches")
        identity_risk = swapped and (signal("ownership_confirmed") is False or matches is False or signal("number_verified") is False)
        evidence: dict[str, Any]
        if action.kind == "verify_location":
            evidence = {"verification": "UNKNOWN" if matches is None else "TRUE" if matches else "FALSE",
                        "zone": node.zone if matches else "unexpected-zone" if matches is False else "unknown"}
            summary = f"Location verified · {node.zone}" if matches else "Location mismatch; endpoint trust reduced" if matches is False else "No location observation supplied"
        elif action.kind == "sim_swap":
            evidence = {"swapped_in_24h": swapped, "minutes_since_swap": minutes,
                        "derived_risk": "HIGH" if identity_risk else "LOW", "observation_available": minutes is not None}
            summary = "Recent SIM change · trust reduced" if identity_risk else "No correlated suspicious SIM change"
        elif action.kind == "number_verify":
            value = signal("number_verified")
            evidence = {"verified": value, "identity_proof": False}
            summary = "Authenticated mobile-line context matches" if value is True else "Number context unverified; additional verification required"
        elif action.kind == "device_swap":
            value = signal("device_changed")
            evidence = {"device_changed": value, "observation_available": value is not None}
            summary = "Device association changed" if value is True else "No device association change observed" if value is False else "No device association observation supplied"
        elif action.kind == "device_status":
            value = signal("device_reachable", node.operational)
            evidence = {"reachable": value, "operational": node.operational}
            summary = f"{node.name} reachability: {'reachable' if value else 'unreachable'} (simulated)"
        elif action.kind == "edge_discovery":
            distances = {node.id: 0}
            queue = deque([node.id])
            while queue:
                current = queue.popleft()
                for edge in incident.topology.edges:
                    if edge.enabled and edge.carries_service and current in (edge.source, edge.target):
                        neighbor = edge.target if edge.source == current else edge.source
                        if neighbor not in distances:
                            distances[neighbor] = distances[current] + 1
                            queue.append(neighbor)
            candidates = sorted((n for n in incident.topology.nodes if n.kind == "edge" and n.operational
                                 and n.state not in (SecurityState.ISOLATED, SecurityState.OFFLINE) and n.id in distances),
                                key=lambda n: (distances[n.id], n.id))
            selected = candidates[0] if candidates else None
            evidence = {"edge_id": selected.id if selected else None, "hops": distances[selected.id] if selected else None,
                        "candidates": [n.id for n in candidates], "deployed": False}
            summary = f"Reachable edge discovered: {selected.name}" if selected else "No reachable edge is available in this twin"
        elif action.kind == "reroute":
            evidence = {"route": "protected-core-path", "service": node.id}
            summary = f"{node.name} moved to protected transport"
        elif action.kind == "qod":
            evidence = {"profile": "EMERGENCY_DEMO", "latency_before_ms": node.latency_ms, "latency_after_ms": min(node.latency_ms, 8)}
            summary = f"{node.name} priority active · {node.latency_ms} → {evidence['latency_after_ms']} ms (simulated)"
        elif action.kind in ("quarantine", "isolate_segment"):
            evidence = {"isolated": True, "scope": "endpoint" if action.kind == "quarantine" else "shared-segment"}
            summary = f"{node.name} {'quarantined' if action.kind == 'quarantine' else 'segment isolated after route protection'}"
        elif action.kind == "restrict_session":
            evidence = {"restricted": True, "scope": "affected-session", "trust": "RESTRICTED", "trust_score": min(node.trust_score, 20)}
            summary = f"{node.name} session restricted; shared services remain available"
        elif action.kind == "step_up":
            evidence = {"verification_required": True, "verified": False}
            summary = f"{node.name} requires additional verification; identity has not been confirmed"
        elif action.kind == "stabilize":
            evidence = {"stabilized": True, "latency_before_ms": node.latency_ms, "latency_after_ms": min(node.latency_ms, 20)}
            summary = f"{node.name} operational load stabilized in the local model"
        else:
            raise ValueError("Capability has no installed simulator")
        result = CapabilityResult(provider=self.name, mode=self.mode, simulated=True,
            capability=action.kind, summary=summary, evidence=evidence).model_dump()
        result.update(evidence)  # v1 clients read evidence keys at top level.
        self._completed[key] = (signature, deepcopy(result))
        return result
