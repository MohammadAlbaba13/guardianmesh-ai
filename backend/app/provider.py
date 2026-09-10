"""Conceptual local capabilities. This module never opens a network connection."""
from typing import Protocol, Any
from .models import Action, Incident
from .topology import asset

ENDPOINTS = {
    "verify_location": "/device/location/verify", "sim_swap": "/sim-swap/check",
    "reroute": "/routes/reroute", "qod": "/qod/sessions",
    "quarantine": "/slice/isolate", "isolate_segment": "/slice/isolate",
}


class NetworkProvider(Protocol):
    name: str
    simulated: bool

    async def execute(self, action: Action, incident: Incident) -> dict[str, Any]: ...


class SimulatedNetworkProvider:
    name = "Local deterministic Network-as-Code simulator"
    simulated = True

    def __init__(self) -> None:
        self._completed: dict[tuple[str, str], dict[str, Any]] = {}

    async def execute(self, action: Action, incident: Incident) -> dict[str, Any]:
        key = (incident.id, action.id)
        if key in self._completed:
            return dict(self._completed[key])
        if action.kind not in ENDPOINTS or action.endpoint != ENDPOINTS[action.kind]:
            raise ValueError("Unsupported simulated operation")
        node = asset(incident.topology, action.target)
        if action.kind in ("quarantine", "isolate_segment") and node.critical:
            raise ValueError("Critical-service isolation is forbidden")
        telemetry = incident.telemetry
        swapped = telemetry.sim_swap_minutes_ago is not None and telemetry.sim_swap_minutes_ago <= 1440
        location_mismatch = not telemetry.location_matches
        identity_risk = swapped and (not telemetry.ownership_confirmed or location_mismatch)
        results = {
            "verify_location": {"verification": "FALSE" if location_mismatch else "TRUE", "zone": "unexpected-zone" if location_mismatch else node.zone,
                                "summary": "Location mismatch; endpoint trust reduced" if location_mismatch else f"Location verified · {node.zone}"},
            "sim_swap": {"swapped_in_24h": swapped, "minutes_since_swap": telemetry.sim_swap_minutes_ago,
                         "derived_risk": "HIGH" if identity_risk else "LOW", "summary": "Recent SIM change · trust reduced" if identity_risk else "No suspicious SIM change · low identity risk"},
            "reroute": {"route": "protected-core-path", "service": node.id, "summary": f"{node.name} moved to protected transport"},
            "qod": {"profile": "EMERGENCY_DEMO", "latency_before_ms": 45, "latency_after_ms": 8,
                    "summary": f"{node.name} priority active · 45 → 8 ms (simulated)"},
            "quarantine": {"isolated": True, "scope": "endpoint", "summary": f"{node.name} quarantined"},
            "isolate_segment": {"isolated": True, "scope": "shared-segment", "summary": f"{node.name} segment isolated after route protection"},
        }
        result = {"simulated": True, "provider": self.name, **results[action.kind]}
        self._completed[key] = result
        return dict(result)
