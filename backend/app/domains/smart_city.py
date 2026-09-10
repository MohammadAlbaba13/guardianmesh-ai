from ..models import Asset, Link, Topology, SecurityState
from ..models import DomainMetadata, Telemetry
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy


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
    for node in nodes:
        node.shared = node.id in ("telecom", "edge", "core", "city")
        node.priority = 1 if node.id in ("hospital", "emergency") else 3
    return Topology(nodes=nodes, edges=edges, service_roots=["core"], preferred_targets=["hospital", "emergency"])


SCENARIOS = {
    "camera": Scenario("camera", "Compromised IoT Camera", "Lateral movement · hospital exposure", "camera", .96,
        "IoT lateral movement", .97,
        ("Camera opened 48 unauthorized remote-service sessions in 10 seconds; baseline is 2.",
         "Simulated exploit signature observed against the telecom gateway remote service.",
         "Destination route leads to hospital and emergency service dependencies."),
        "T1210", "Exploitation of Remote Services", "Lateral Movement",
        "An exploit signature and unauthorized remote-service attempts indicate attempted lateral movement, not scanning alone."),
    "identity": Scenario("identity", "Telecom Identity / SIM-Swap Risk", "Identity anomaly · trusted endpoint", "sensor", .88,
        "Suspected telecom identity takeover", .91,
        ("Trusted sensor identity re-registered from an unexpected city zone.",
         "SIM replacement occurred 12 minutes before the authentication anomaly.",
         "Owner-confirmation flag is absent in the synthetic identity record."),
        "T1451", "SIM Card Swap", "Initial Access",
        "A recent SIM change plus an unconfirmed identity transfer and location anomaly supports a suspected SIM-swap mapping. A SIM change alone is not proof of compromise.", "Mobile", category="IDENTITY"),
    "energy": Scenario("energy", "Energy & City Control Threat", "Control-plane abuse · shared segment", "traffic", .99,
        "Unauthorized infrastructure control", .98,
        ("Traffic controller sent 26 unauthorized service-stop requests to the edge compute plane.",
         "Command source is outside the signed controller maintenance window.",
         "Shared edge segment supplies energy telemetry and smart-city control."),
        "T1489", "Service Stop", "Impact",
        "Unauthorized service-stop commands attempt to disrupt the edge services supporting energy and city control. This is an Enterprise mapping for the compute layer, not a full ICS assessment.",
        requires_approval=True,
        response_policy=ResponsePolicy(priority_targets=("energy",), shared_target="edge")),
}


def scenario_telemetry(scenario_id: str) -> Telemetry:
    return {
        "camera": Telemetry(remote_sessions=48, baseline_sessions=2, exploit_signature=True),
        "identity": Telemetry(sim_swap_minutes_ago=12, ownership_confirmed=False, location_matches=False),
        "energy": Telemetry(service_stop_requests=26, maintenance_window=False),
    }[scenario_id]


def camera_evidence(t: Telemetry) -> list[str]:
    return [f"Camera opened {t.remote_sessions} unauthorized remote-service sessions in 10 seconds; baseline is {t.baseline_sessions}.",
            *SCENARIOS["camera"].evidence[1:]]


def identity_evidence(t: Telemetry) -> list[str]:
    return [SCENARIOS["identity"].evidence[0],
            f"SIM replacement occurred {t.sim_swap_minutes_ago} minutes before the authentication anomaly.",
            SCENARIOS["identity"].evidence[2]]


def energy_evidence(t: Telemetry) -> list[str]:
    return [f"Traffic controller sent {t.service_stop_requests} unauthorized service-stop requests to the edge compute plane.",
            *SCENARIOS["energy"].evidence[1:]]


PACK = DomainPack(
    metadata=DomainMetadata(id="smart_city", name="Smart Cities & Urban Safety", theme="Smart Cities & Urban Safety",
        value_proposition="Contain infrastructure threats while preserving essential city services.",
        tagline="A compromised camera. A protected hospital. A city that stays connected.",
        twin_title="Urban resilience digital twin", services_label="Critical services online", risk_label="Propagation risk",
        event_label="Infrastructure threat", report_label="City resilience incident report", outcome_label="Critical services protected",
        accent="#34d399", icon="city"),
    topology_factory=build_topology, scenarios=SCENARIOS,
    permitted_capabilities=("verify_location","sim_swap","reroute","qod","quarantine","isolate_segment"),
    response_policy=ResponsePolicy(priority_targets=("hospital","emergency")),
    legacy_telemetry=scenario_telemetry,
    detection_rules=(
        DetectionRule("camera", lambda t: t.remote_sessions>5*t.baseline_sessions and t.exploit_signature, camera_evidence),
        DetectionRule("identity", lambda t: t.sim_swap_minutes_ago is not None and t.sim_swap_minutes_ago<=1440 and not t.ownership_confirmed and not t.location_matches, identity_evidence),
        DetectionRule("energy", lambda t: t.service_stop_requests>=10 and not t.maintenance_window, energy_evidence),
    ),
)
