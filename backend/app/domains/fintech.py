"""Secure Fintech: network evidence informs a bounded payment-session trust response."""
from ..models import DomainMetadata, Metric
from .base import DomainPack, Scenario, DetectionRule, ResponsePolicy, SignalDefinition as S, topology_from_specs, trust_metrics


def build_topology():
    return topology_from_specs([
        ("payment_session","Customer Payment Session","device","customer",False,.7,.95,0,160),
        ("mobile_network","Mobile Network","core","network",False,.8,.5,235,160),
        ("bank_identity","Bank Trust Gateway","identity","bank-edge",False,.9,.6,470,160),
        ("authentication","Bank Authentication","identity","banking",True,.95,.75,705,0),
        ("fraud_engine","Fraud Decision Service","bank","banking",True,.95,.8,705,300),
        ("banking_platform","Banking Platform","gateway","banking",False,.95,.65,950,160),
        ("payment_gateway","Payment Gateway","payment","payments",True,1,.9,1190,80),
        ("core_banking","Core Banking","bank","ledger",True,1,.8,1190,260),
        ("merchant","Merchant Settlement View","payment","merchant",False,.7,.5,1190,440),
        ("case_review","Fraud Case Review","guardian","oversight",False,.6,.2,470,420),
    ], [("payment_session","mobile_network","identity"),("mobile_network","bank_identity","identity"),
        ("bank_identity","authentication","identity"),("bank_identity","fraud_engine","identity"),
        ("authentication","banking_platform","data"),("fraud_engine","banking_platform","data"),
        ("banking_platform","payment_gateway","data"),("payment_gateway","core_banking","data"),
        ("core_banking","merchant","data"),("case_review","fraud_engine","management")],
        roots=["mobile_network"],priorities=["authentication","payment_gateway"],shared=("mobile_network","bank_identity","banking_platform"),trusted=("payment_session",))


SCENARIO=Scenario("high_value_payment","High-Value Payment After SIM Change","Payment exposure · new device · location mismatch",
    "payment_session",.97,"High-risk payment session with reduced identity confidence",.96,(),
    explanation="Payment amount and abnormal authentication context are correlated with recent SIM/device change and location mismatch. The result restricts only a synthetic session; it does not reverse funds or control a bank.",
    category="FRAUD",signal_values={"payment_amount":48000,"sim_swap_minutes_ago":6,"device_changed":True,
        "location_matches":False,"number_verified":False,"authentication_attempts":7})


def metrics(incident):
    return trust_metrics(incident)+[Metric(id="payment_exposure",label="Payment under review",value=incident.telemetry.get("payment_amount",0),
        unit="USD equivalent",direction="neutral",description="Synthetic transaction context, not money moved or recovered.")]


PACK=DomainPack(
    metadata=DomainMetadata(id="fintech",name="Secure Fintech & Anti-Fraud",theme="Secure Fintech & Anti-Fraud",
        value_proposition="Turn telecom identity signals into auditable fraud decisions without disrupting banking infrastructure.",
        tagline="A high-value payment. A changed identity context. A bounded trust response.",twin_title="Financial trust digital twin",
        services_label="Financial services protected",risk_label="Transaction propagation risk",event_label="Payment trust event",
        report_label="Anti-fraud incident report",outcome_label="Banking continuity preserved",accent="#a78bfa",icon="fintech"),
    topology_factory=build_topology,scenarios={SCENARIO.id:SCENARIO},
    permitted_capabilities=("sim_swap","device_swap","verify_location","number_verify","reroute","qod","restrict_session","step_up"),
    response_policy=ResponsePolicy(context_capabilities=("sim_swap","device_swap","number_verify","verify_location"),
        priority_targets=("authentication","payment_gateway"),remediation=("restrict_session","step_up"),
        strategy="Correlate fraud evidence, preserve banking routes, restrict only the suspicious payment session"),
    signal_schema=(S("payment_amount","Payment amount","number","USD equivalent",minimum=0),
        S("sim_swap_minutes_ago","Time since SIM replacement","integer","min",minimum=0),S("device_changed","Device changed","boolean"),
        S("location_matches","Expected location matches","boolean"),S("number_verified","Number verification","boolean"),
        S("authentication_attempts","Abnormal authentication attempts","integer",minimum=0)),
    detection_rules=(DetectionRule(SCENARIO.id,
        lambda t:t.get("payment_amount")>=10000 and t.get("sim_swap_minutes_ago")<=1440 and t.get("device_changed") and not t.get("location_matches") and not t.get("number_verified"),
        lambda t:[f"Synthetic payment amount: {t.get('payment_amount')} USD equivalent; authentication attempts: {t.get('authentication_attempts')}.",
                  f"SIM changed {t.get('sim_swap_minutes_ago')} minutes ago; new device: {t.get('device_changed')}.",
                  f"Location matches: {t.get('location_matches')}; number verification: {t.get('number_verified')}."]),),
    extra_metrics=metrics,
)
