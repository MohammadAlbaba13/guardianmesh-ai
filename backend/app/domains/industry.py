"""Defensive industrial edge resilience with a real shared-infrastructure gate."""
from ..models import DomainMetadata, Metric
from ..topology import asset
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs


def build_topology():
    return topology_from_specs([
        ("edge_controller","Industrial Edge Controller","control","machine",False,.75,.9,0,100),
        ("industrial_sensor","Production Sensor","sensor","machine",False,.5,.6,0,320),
        ("private_access","Private 5G Access","core","private-network",False,.95,.4,240,160),
        ("edge_compute","Factory Edge Compute","edge","factory-edge",False,.9,.7,480,160),
        ("factory_gateway","Shared Factory Gateway","gateway","factory",False,.95,.75,720,160),
        ("production_line","Production Line","industry","production",True,.95,.8,970,0),
        ("robotics","Robotics Coordination","control","production",True,.95,.8,970,150),
        ("enterprise_systems","Enterprise Operations","application","enterprise",True,.8,.65,970,300),
        ("safety_service","Safety Interlock Service","safety","safety",True,1,.9,720,420),
        ("maintenance","Signed Maintenance Console","guardian","oversight",False,.7,.2,480,420),
    ],[("edge_controller","private_access","control"),("industrial_sensor","private_access","data"),
       ("private_access","edge_compute","data"),("edge_compute","factory_gateway","control"),
       ("factory_gateway","production_line","control"),("factory_gateway","robotics","control"),
       ("factory_gateway","enterprise_systems","data"),("factory_gateway","safety_service","control"),
       ("maintenance","factory_gateway","management")],roots=["private_access"],priorities=["safety_service","production_line"],
       shared=("private_access","edge_compute","factory_gateway"))


SCENARIO=Scenario("edge_controller", "Industrial Edge Control Abuse", "Unauthorized service stops · production dependencies",
    "edge_controller", .98, "Unauthorized edge service-stop commands", .98, (),
    "T1489", "Service Stop", "Impact",
    "Unscheduled commands attempt to stop enterprise services on factory edge compute. T1489 describes the compute-layer behavior; this is not a claim of an ICS-specific exploit or physical plant control.",
    requires_approval=True,category="CYBER",signal_values={"service_stop_requests":31,"unauthorized_control_commands":42,
        "maintenance_window":False,"device_reachable":True,"signed_command":False})


def metrics(incident):
    services=[asset(incident.topology,n) for n in ("production_line","robotics")]
    return [Metric(id="production_continuity",label="Production systems operational",value=sum(n.operational for n in services),
        unit="/ 2",direction="higher",description="Modeled production line and robotics availability; no physical production is controlled."),
        Metric(id="safety_available",label="Safety service available",value=int(asset(incident.topology,"safety_service").operational),
        direction="higher",description="Safety communications are protected before shared gateway isolation.")]


PACK=DomainPack(metadata=DomainMetadata(id="industry",name="Industrial & Enterprise AI",theme="Industrial & Enterprise AI Automation",
    value_proposition="Contain abnormal edge control while preserving production and safety communications.",
    tagline="Protect safety first. Bound edge containment. Keep production connected.",twin_title="Industrial continuity digital twin",
    services_label="Industrial services online",risk_label="Production dependency risk",event_label="Industrial control threat",
    report_label="Industrial operational impact report",outcome_label="Production and safety continuity preserved",accent="#fb923c",icon="industry"),
    topology_factory=build_topology,scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("device_status","edge_discovery","reroute","qod","isolate_segment","quarantine"),
    response_policy=ResponsePolicy(context_capabilities=("device_status","edge_discovery"),priority_targets=("safety_service","production_line"),
        shared_target="factory_gateway",life_safety_first=True,
        strategy="Protect safety and production routes, seek approval for the shared gateway, and isolate only the compromised controller",
        rationale="The shared gateway affects multiple factory services. Approval is required after a dry-run proves protected continuity; rejection retains the gateway and contains only the endpoint."),
    signal_schema=(S("service_stop_requests","Unauthorized service stops","integer",minimum=0),
        S("unauthorized_control_commands","Unexpected control commands","integer",minimum=0),S("maintenance_window","Within signed maintenance window","boolean"),
        S("device_reachable","Controller reachable","boolean"),S("signed_command","Commands signed","boolean")),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t:t.get("service_stop_requests")>=10 and t.get("unauthorized_control_commands")>=20 and not t.get("maintenance_window") and not t.get("signed_command"),
        lambda t:[f"Observed {t.get('service_stop_requests')} service-stop requests among {t.get('unauthorized_control_commands')} unexpected control commands.",
                  f"Signed maintenance window: {t.get('maintenance_window')}; command signature valid: {t.get('signed_command')}.",
                  "Factory gateway dependencies include production, robotics, enterprise operations and the safety interlock service."]),),
    extra_metrics=metrics)
