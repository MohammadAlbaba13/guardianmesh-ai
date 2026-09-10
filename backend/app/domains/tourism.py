"""Visitor trust and experience continuity, without inventing a cyberattack."""
from ..models import DomainMetadata, Metric
from ..topology import asset
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs, trust_metrics


def build_topology():
    twin = topology_from_specs([
        ("tourist_device","Tourist Device","device","visitor",False,.5,.85,0,160),
        ("visitor_network","Visitor Mobile Network","core","network",False,.8,.5,240,160),
        ("tourism_edge","Tourism Edge Platform","edge","venue-edge",False,.85,.65,480,160),
        ("tourist_identity","Digital Tourist Identity","identity","trust",True,.8,.7,720,0),
        ("booking_access","Booking & Venue Access","application","venue",True,.75,.8,960,0),
        ("cultural_ar","Cultural AR Experience","application","culture",True,.8,.8,720,220),
        ("smart_venue","Smart Heritage Venue","gateway","venue",False,.6,.65,960,220),
        ("visitor_emergency","Visitor Emergency Assistance","emergency","assistance",True,1,.85,720,440),
        ("content_edge","Local Culture Content Edge","edge","culture",False,.5,.3,480,440),
    ],[("tourist_device","visitor_network","identity"),("visitor_network","tourism_edge","data"),
       ("tourism_edge","tourist_identity","identity"),("tourist_identity","booking_access","identity"),
       ("tourism_edge","cultural_ar","data"),("cultural_ar","smart_venue","data"),
       ("tourism_edge","visitor_emergency","data"),("content_edge","cultural_ar","management")],
       roots=["visitor_network"],priorities=["visitor_emergency","cultural_ar"],shared=("visitor_network","tourism_edge"),trusted=("tourist_device",))
    asset(twin,"cultural_ar").latency_ms = 180
    return twin


SCENARIO = Scenario("visitor_experience", "Visitor Trust & Cultural Experience Degradation",
    "Location inconsistency · degraded immersive experience", "tourist_device", .83,
    "Visitor trust inconsistency with experience degradation", .94, (), category="OPERATIONAL",
    explanation="An unexpected visitor location and unverified number coincide with elevated cultural AR latency. This is an operational trust event, not evidence of a cyberattack. Emergency access must remain available while the visitor completes additional verification.",
    signal_values={"location_matches":False,"number_verified":False,"device_reachable":True,"experience_latency_ms":180,"baseline_latency_ms":35})


def metrics(incident):
    return trust_metrics(incident) + [Metric(id="experience_latency",label="Cultural experience latency",
        value=asset(incident.topology,"cultural_ar").latency_ms,unit="ms",direction="lower",
        description="Actual digital-twin AR flow latency; QoD is a local simulation."),
        Metric(id="emergency_access",label="Visitor emergency availability",value=int(asset(incident.topology,"visitor_emergency").operational),
        unit="",direction="higher",description="Must remain available during visitor verification.")]


def verify(incident):
    return (["Visitor emergency assistance was interrupted."] if not asset(incident.topology,"visitor_emergency").operational else []) + (
        ["Cultural experience latency did not improve."] if asset(incident.topology,"cultural_ar").latency_ms >= incident.telemetry.get("experience_latency_ms") else [])


PACK = DomainPack(
    metadata=DomainMetadata(id="tourism",name="Tourism & Cultural Experience",theme="Tourism & Cultural Experience Innovation",
        value_proposition="Preserve connected cultural experiences and emergency access while validating visitor trust.",
        tagline="A trusted visitor journey. A responsive cultural experience. Assistance always accessible.",
        twin_title="Connected visitor digital twin",services_label="Visitor services available",risk_label="Experience dependency risk",
        event_label="Visitor trust and connectivity event",report_label="Visitor experience continuity report",
        outcome_label="Visitor experience protected",accent="#f472b6",icon="tourism"),
    topology_factory=build_topology,scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("verify_location","number_verify","device_status","edge_discovery","reroute","qod","restrict_session","step_up"),
    response_policy=ResponsePolicy(context_capabilities=("verify_location","number_verify","device_status","edge_discovery"),
        priority_targets=("visitor_emergency","cultural_ar"),remediation=("restrict_session","step_up"),life_safety_first=True,
        strategy="Keep emergency assistance reachable, prioritize the cultural experience and require bounded visitor verification",
        rationale="Location inconsistency reduces only the affected visitor's session trust; shared venue services and emergency access remain operational."),
    signal_schema=(S("location_matches","Visitor location matches","boolean"),S("number_verified","Visitor number verified","boolean"),
        S("device_reachable","Visitor device reachable","boolean"),S("experience_latency_ms","AR experience latency","integer","ms",minimum=0),
        S("baseline_latency_ms","Normal AR latency","integer","ms",minimum=1)),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t:not t.get("location_matches") and not t.get("number_verified") and t.get("experience_latency_ms")>2*t.get("baseline_latency_ms"),
        lambda t:[f"Visitor location matches: {t.get('location_matches')}; number verified: {t.get('number_verified')}.",
                  f"Cultural AR latency {t.get('experience_latency_ms')} ms exceeds twice its {t.get('baseline_latency_ms')} ms baseline.",
                  f"Visitor device remains reachable: {t.get('device_reachable')}; emergency accessibility must be preserved."]),),
    extra_metrics=metrics,extra_verify=verify)
