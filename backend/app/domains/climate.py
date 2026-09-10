"""Flood-driven congestion response preserves sensors and emergency communication."""
from ..models import DomainMetadata, Metric
from ..topology import asset
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs


def build_topology():
    twin=topology_from_specs([
        ("flood_sensor","Flood Monitoring Sensor","sensor","river",False,.8,.85,0,120),
        ("weather_station","Weather Station","sensor","weather",False,.7,.65,0,340),
        ("iot_access","Mobile IoT Access","core","regional-network",False,.95,.55,240,180),
        ("climate_edge","Environmental Edge Processing","edge","emergency-edge",False,.85,.7,480,180),
        ("coordination","Emergency Coordination","gateway","response",False,1,.75,720,180),
        ("civil_defense","Civil Defense Dispatch","emergency","response",True,1,.95,970,0),
        ("field_hospital","Field Hospital Communications","hospital","health",True,1,.9,970,150),
        ("energy_resilience","Energy Resilience Service","energy","infrastructure",True,.9,.7,970,300),
        ("evacuation","Evacuation Coordination","emergency","evacuation",True,1,.9,720,450),
        ("public_warning","Public Warning Broadcast","safety","public",True,.95,.8,480,450),
    ],[("flood_sensor","iot_access","data"),("weather_station","iot_access","data"),
       ("iot_access","climate_edge","data"),("climate_edge","coordination","data"),
       ("coordination","civil_defense","data"),("coordination","field_hospital","data"),
       ("coordination","energy_resilience","data"),("coordination","evacuation","data"),
       ("coordination","public_warning","data")],roots=["iot_access"],
       priorities=["civil_defense","field_hospital","evacuation","public_warning"],shared=("iot_access","climate_edge","coordination"))
    for node in twin.nodes:
        if node.critical: node.latency_ms=220
    return twin


SCENARIO=Scenario("flood_congestion", "Flood Alert & Emergency Network Congestion",
    "Rising water · congested network · emergency continuity", "flood_sensor", .97,
    "Flood-driven operational communications disruption", .99, (), category="ENVIRONMENTAL",
    explanation="A flood threshold breach coincides with saturated access and delayed emergency traffic. This models a climate-driven disruption, not a cyberattack; risk is downstream dependency exposure, and mitigation cannot remove the flood.",
    signal_values={"water_level_cm":285,"flood_threshold_cm":180,"rainfall_mm_hour":74,
        "congestion_percent":94,"emergency_latency_ms":220,"location_matches":True,"device_reachable":True})


def metrics(incident):
    source=asset(incident.topology,incident.source)
    return [Metric(id="water_level",label="Measured flood level",value=incident.telemetry.get("water_level_cm"),unit="cm",
        direction="neutral",description="Environmental evidence remains unchanged; network mitigation does not remove floodwater."),
        Metric(id="modeled_congestion",label="Modeled access congestion",value=35 if source.state=="PROTECTED" else incident.telemetry.get("congestion_percent"),
        unit="%",direction="lower",description="Local stabilization model reduces congestion to 35%; this is not a carrier capacity measurement."),
        Metric(id="sensor_ingestion",label="Sensor ingestion available",value=int(source.operational and any(
            e.source==source.id and e.enabled and e.carries_service for e in incident.topology.edges)),direction="higher",
            description="Sensor data remains enabled throughout emergency response.")]


def verify(incident):
    source=asset(incident.topology,incident.source)
    return [] if source.operational and any(e.source==source.id and e.enabled and e.carries_service for e in incident.topology.edges) else ["Flood sensor ingestion was disabled during emergency response."]


PACK=DomainPack(metadata=DomainMetadata(id="climate",name="Climate Resilience",theme="Climate Resilience",
    value_proposition="Keep emergency coordination, public warnings and sensor data available during climate-driven congestion.",
    tagline="Respond to the flood. Preserve communications. Keep environmental evidence flowing.",twin_title="Climate emergency digital twin",
    services_label="Emergency services available",risk_label="Disruption dependency risk",event_label="Environmental disruption",
    report_label="Climate resilience response report",outcome_label="Emergency communications preserved",accent="#22d3ee",icon="climate"),
    topology_factory=build_topology,scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("verify_location","device_status","edge_discovery","reroute","qod","stabilize"),
    response_policy=ResponsePolicy(context_capabilities=("device_status","verify_location","edge_discovery"),
        priority_targets=("civil_defense","field_hospital","evacuation","public_warning"),remediation=("stabilize",),life_safety_first=True,
        strategy="Protect emergency routes, prioritize essential traffic and stabilize congestion without isolating environmental sensors",
        rationale="The source is environmental telemetry, not a hostile endpoint. Isolation is prohibited; protected routes and simulated prioritization preserve emergency accessibility."),
    signal_schema=(S("water_level_cm","Observed water level","integer","cm",minimum=0),
        S("flood_threshold_cm","Flood alert threshold","integer","cm",minimum=1),S("rainfall_mm_hour","Rainfall intensity","number","mm/h",minimum=0),
        S("congestion_percent","Access congestion","integer","%",minimum=0,maximum=100),S("emergency_latency_ms","Emergency traffic latency","integer","ms",minimum=0),
        S("location_matches","Sensor location verified","boolean"),S("device_reachable","Sensor reachable","boolean")),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t:t.get("water_level_cm")>=t.get("flood_threshold_cm") and t.get("congestion_percent")>=80 and t.get("emergency_latency_ms")>=100,
        lambda t:[f"Water level {t.get('water_level_cm')} cm exceeds the {t.get('flood_threshold_cm')} cm flood threshold; rainfall {t.get('rainfall_mm_hour')} mm/h.",
                  f"Access congestion {t.get('congestion_percent')}%; emergency flow latency {t.get('emergency_latency_ms')} ms.",
                  "Environmental conditions require emergency prioritization, not cyber attribution or sensor quarantine."]),),
    extra_metrics=metrics,extra_verify=verify)
