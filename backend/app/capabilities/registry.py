"""Semantic catalog. Legacy endpoint values are display labels, not HTTP routes."""
from pydantic import BaseModel, ConfigDict
from typing import Literal


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    name: str
    description: str
    endpoint: str
    conceptual: bool = False
    documentation_url: str | None = None
    mode: Literal["SIMULATED"] = "SIMULATED"


def _item(id: str, name: str, description: str, endpoint: str | None = None,
          documentation_url: str | None = None, conceptual: bool = False) -> Capability:
    return Capability(id=id, name=name, description=description,
                      endpoint=endpoint or f"capability://{id}",
                      conceptual=conceptual, documentation_url=documentation_url)


_CATALOG = [
    _item("verify_location", "Location Verification", "Check expected device area. Simulator uses supplied location-match evidence.",
          "/device/location/verify", "https://camaraproject.org/location-verification/"),
    _item("sim_swap", "SIM Swap", "Check recent SIM change; GuardianMesh derives correlated risk separately.",
          "/sim-swap/check", "https://camaraproject.org/sim-swap/"),
    _item("number_verify", "Number Verification", "Verify authenticated mobile-line context; not full identity proof.",
          documentation_url="https://camaraproject.org/number-verification/"),
    _item("device_swap", "Device Swap", "Check mobile-line to physical-device association change.",
          documentation_url="https://camaraproject.org/device-swap/"),
    _item("device_status", "Device Reachability Status", "Check data reachability in the local model.",
          documentation_url="https://camaraproject.org/device-reachability-status/"),
    _item("edge_discovery", "Simple Edge Discovery", "Discover reachable edge by network path; does not deploy an application.",
          documentation_url="https://camaraproject.org/simple-edge-discovery/"),
    _item("qod", "Quality on Demand", "Prioritize a selected flow. Simulated latency is not an operator guarantee.",
          "/qod/sessions", "https://camaraproject.org/quality-on-demand/"),
    _item("reroute", "Protected Routing", "Activate declared protected transport in the local twin.", "/routes/reroute", conceptual=True),
    _item("quarantine", "Endpoint Quarantine", "Contain a non-critical simulation source; no generic CAMARA quarantine API.", "/slice/isolate", conceptual=True),
    _item("isolate_segment", "Shared Segment Isolation", "Isolate a simulation segment after route protection and matching approval.", "/slice/isolate", conceptual=True),
    _item("restrict_session", "Bounded Session Protection", "Restrict the affected simulated session while shared infrastructure stays available.", conceptual=True),
    _item("step_up", "Step-up Verification", "Require additional application verification; never invent successful identity proof.", conceptual=True),
    _item("stabilize", "Operational Stabilization", "Reduce modeled congestion after protection; a local resilience control.", conceptual=True),
]
_REGISTRY = {item.id: item for item in _CATALOG}
assert len(_REGISTRY) == len(_CATALOG), "Capability IDs must be unique"


def get_capability(capability_id: str) -> Capability:
    try:
        return _REGISTRY[capability_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported capability: {capability_id}") from exc


capability = get_capability


def list_capabilities() -> list[Capability]:
    return list(_CATALOG)
