"""Trusted Digital Identity: isolate suspicious trust context, not citizen services."""
from ..models import DomainMetadata
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs, trust_metrics


def build_topology():
    return topology_from_specs([
        ("citizen_device","Citizen Mobile Device","device","subscriber",False,.55,.9,0,150),
        ("mobile_access","Mobile Identity Network","core","network",False,.8,.55,240,150),
        ("identity_gateway","Identity Gateway","gateway","trust",False,.9,.6,480,150),
        ("trust_broker","Trust Verification Broker","identity","trust",False,.9,.5,720,150),
        ("identity_provider","Digital Identity Provider","identity","identity",True,1,.8,970,0),
        ("citizen_portal","Citizen Services","government","government",True,.95,.75,970,150),
        ("cross_border","Cross-Border Verification","identity","border",True,.9,.7,970,300),
        ("protected_app","Protected Application","application","application",True,.85,.7,720,410),
        ("audit_service","Trust Audit Service","guardian","oversight",False,.6,.2,480,410),
    ], [("citizen_device","mobile_access","identity"),("mobile_access","identity_gateway","identity"),
        ("identity_gateway","trust_broker","identity"),("trust_broker","identity_provider","identity"),
        ("trust_broker","citizen_portal","data"),("trust_broker","cross_border","identity"),
        ("citizen_portal","protected_app","data"),("audit_service","trust_broker","management")],
        roots=["mobile_access"], priorities=["identity_provider","citizen_portal"],
        shared=("mobile_access","identity_gateway","trust_broker"),trusted=("citizen_device",))


SCENARIO = Scenario("re_registration", "Suspicious Identity Re-Registration", "Recent SIM + device change · ownership unconfirmed",
    "citizen_device", .9, "Suspected identity re-registration takeover", .95, (),
    "T1451", "SIM Card Swap", "Initial Access",
    "A recent SIM replacement, new device, missing owner confirmation and inconsistent location jointly indicate a suspected identity takeover. No single network signal proves identity.",
    "Mobile", category="IDENTITY", signal_values={"sim_swap_minutes_ago":8,"device_changed":True,
        "location_matches":False,"ownership_confirmed":False,"number_verified":False,"registration_attempts":5})

PACK = DomainPack(
    metadata=DomainMetadata(id="identity",name="Trusted Digital Identity",theme="Trusted Digital Identity",
        value_proposition="Correlate network trust signals before a suspicious identity reaches citizen services.",
        tagline="Lower the suspicious session's trust. Keep citizen services available.",twin_title="Identity trust digital twin",
        services_label="Identity services protected",risk_label="Trust propagation risk",event_label="Identity trust event",
        report_label="Identity assurance report",outcome_label="Identity services protected",accent="#38bdf8",icon="identity"),
    topology_factory=build_topology, scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("sim_swap","device_swap","verify_location","number_verify","reroute","qod","restrict_session","step_up"),
    response_policy=ResponsePolicy(context_capabilities=("sim_swap","device_swap","verify_location","number_verify"),
        priority_targets=("identity_provider",),remediation=("restrict_session","step_up"),
        strategy="Correlate identity evidence, protect citizen services, restrict the affected session and require step-up verification"),
    signal_schema=(S("sim_swap_minutes_ago","Time since SIM replacement","integer","min",minimum=0),
        S("device_changed","New device association","boolean"),S("location_matches","Expected location matches","boolean"),
        S("ownership_confirmed","Ownership confirmed","boolean"),S("number_verified","Number matches authenticated line","boolean"),
        S("registration_attempts","Re-registration attempts","integer",minimum=0)),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t: t.get("sim_swap_minutes_ago")<=1440 and t.get("device_changed") and not t.get("location_matches") and not t.get("ownership_confirmed"),
        lambda t:[f"SIM replaced {t.get('sim_swap_minutes_ago')} minutes ago; device association changed: {t.get('device_changed')}.",
                  f"Expected location matches: {t.get('location_matches')}; owner confirmation: {t.get('ownership_confirmed')}.",
                  f"Number verification: {t.get('number_verified')}; re-registration attempts: {t.get('registration_attempts')}."]),),
    extra_metrics=trust_metrics,
)
