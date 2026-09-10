"""Cross-domain trust cascade coordinates life safety and bounded financial trust."""
from ..models import DomainMetadata, Metric
from ..topology import asset
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs, trust_metrics


def build_topology():
    twin=topology_from_specs([
        ("regional_session","Regional Subscriber Session","device","subscriber",False,.7,.95,0,180),
        ("regional_core","Programmable Regional Core","core","common-network",False,.95,.55,240,180),
        ("regional_trust","Cross-Domain Trust Broker","identity","shared-trust",False,.9,.7,480,180),
        ("citizen_identity","Citizen Identity Service","identity","identity",True,.9,.75,720,0),
        ("city_dispatch","Urban Safety Dispatch","safety","smart-city",True,.95,.8,720,170),
        ("payment_service","Regional Payment Service","bank","fintech",True,.9,.85,720,340),
        ("regional_hospital","Regional Hospital Link","hospital","emergency",True,1,.95,970,0),
        ("emergency_dispatch","Cross-Border Emergency Dispatch","emergency","emergency",True,1,.95,970,170),
        ("cultural_service","Connected Culture Service","application","tourism",True,.7,.7,970,340),
        ("regional_oversight","Regional Coordination Desk","guardian","oversight",False,.8,.2,480,440),
    ],[("regional_session","regional_core","identity"),("regional_core","regional_trust","identity"),
       ("regional_trust","citizen_identity","identity"),("regional_trust","city_dispatch","data"),
       ("regional_trust","payment_service","identity"),("city_dispatch","regional_hospital","data"),
       ("city_dispatch","emergency_dispatch","data"),("citizen_identity","cultural_service","data"),
       ("regional_oversight","regional_trust","management")],roots=["regional_core"],
       priorities=["regional_hospital","emergency_dispatch"],shared=("regional_core","regional_trust"),trusted=("regional_session",))
    for node in twin.nodes:
        if node.critical: node.latency_ms=160
    return twin


SCENARIO=Scenario("regional_cascade", "Regional Multi-Service Trust Cascade",
    "Shared identity anomaly · network degradation · cross-domain dependencies", "regional_session", .99,
    "Correlated regional identity and connectivity risk", .97, (), category="IDENTITY",
    explanation="A recent SIM/device change and inconsistent subscriber context coincide with regional network degradation. One shared dependency graph exposes identity, city, fintech, emergency and tourism services. Life-safety routing comes first; financial trust is reduced only for the suspicious session.",
    signal_values={"sim_swap_minutes_ago":4,"device_changed":True,"location_matches":False,"number_verified":False,
        "core_latency_ms":160,"affected_domain_count":5})


def metrics(incident):
    return trust_metrics(incident)+[Metric(id="domains_coordinated",label="Service domains coordinated",value=5,unit="domains",
        description="Identity, Smart City, Fintech, Emergency and Tourism share the authored regional dependency graph."),
        Metric(id="life_safety_online",label="Life-safety links available",value=sum(asset(incident.topology,n).operational for n in ("regional_hospital","emergency_dispatch")),
        unit="/ 2",direction="higher",description="Hospital and emergency links take precedence over lower-priority flows.")]


def policy_errors(plan, incident):
    routes=[a.target for a in plan.actions if a.kind=="reroute"]
    life={"regional_hospital","emergency_dispatch"}
    if not life.issubset(routes) or set(routes[:2])!=life:
        return ["Regional response must protect hospital and emergency routes before other domain services."]
    return []


PACK=DomainPack(metadata=DomainMetadata(id="open_innovation",name="Open Innovation",theme="Open Innovation",
    value_proposition="Coordinate identity, finance, city, emergency and tourism dependencies through one evidence-driven resilience engine.",
    tagline="One shared network. Five service contexts. Life safety first.",twin_title="Regional cross-domain digital twin",
    services_label="Regional services protected",risk_label="Cross-domain cascade risk",event_label="Regional trust cascade",
    report_label="Cross-domain resilience report",outcome_label="Regional continuity and bounded trust preserved",accent="#818cf8",icon="innovation"),
    topology_factory=build_topology,scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("sim_swap","device_swap","verify_location","number_verify","device_status","reroute","qod","restrict_session","step_up"),
    response_policy=ResponsePolicy(context_capabilities=("sim_swap","device_swap","verify_location","number_verify","device_status"),
        priority_targets=("regional_hospital","emergency_dispatch"),remediation=("restrict_session","step_up"),life_safety_first=True,
        strategy="Protect life-safety routes first, preserve cross-domain services and restrict the suspicious regional session",
        rationale="Emergency routing priorities and financial/identity trust boundaries are evaluated together. A single session anomaly cannot authorize shutting down the regional core or payment infrastructure."),
    signal_schema=(S("sim_swap_minutes_ago","Time since SIM replacement","integer","min",minimum=0),
        S("device_changed","Device changed","boolean"),S("location_matches","Location consistent","boolean"),S("number_verified","Subscriber number verified","boolean"),
        S("core_latency_ms","Regional network latency","integer","ms",minimum=0),S("affected_domain_count","Contexts with dependent services","integer",minimum=1,maximum=7)),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t:t.get("sim_swap_minutes_ago")<=1440 and t.get("device_changed") and not t.get("location_matches") and not t.get("number_verified") and t.get("core_latency_ms")>=100 and t.get("affected_domain_count")>=2,
        lambda t:[f"SIM changed {t.get('sim_swap_minutes_ago')} minutes ago; device changed: {t.get('device_changed')}; number verified: {t.get('number_verified')}.",
                  f"Subscriber location consistent: {t.get('location_matches')}; regional latency {t.get('core_latency_ms')} ms.",
                  f"The shared trust/network graph connects {t.get('affected_domain_count')} service contexts, including life-safety and financial services."]),),
    extra_metrics=metrics,extra_policy=policy_errors)
