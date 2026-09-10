import pytest
from pydantic import ValidationError
from app.topology import build_topology, asset, isolate, protect, continuity_verified, online_services
from app.risk import calculate_impact, risk_band
from app.models import Incident, StartRequest, Action, Link, SecurityState, Telemetry
from app.agents import initial_agents, SentinelAgent, ImpactAgent, ResponseAgent, ComplianceAgent
from app.scenarios import SCENARIOS, scenario_telemetry
from app.provider import SimulatedNetworkProvider


def incident_for(scenario="camera"):
    return Incident(id="GM-TEST", scenario_id=scenario, title=SCENARIOS[scenario].title, source=SCENARIOS[scenario].source,
                    mode="fast", auto_approve=True, step_duration=.01, topology=build_topology(), agents=initial_agents(), telemetry=scenario_telemetry(scenario))


def planned(scenario="camera"):
    incident=incident_for(scenario)
    incident.impact=ImpactAgent().analyze(incident)
    incident.plan=ResponseAgent().plan(incident)
    return incident


def test_fourteen_assets_and_six_services():
    twin=build_topology()
    assert len(twin.nodes)==14
    assert online_services(twin)==6
    assert continuity_verified(twin)


def test_directed_graph_reaches_hospital_not_reverse():
    twin=build_topology()
    impact=calculate_impact(twin,"camera",.96)
    hospital=next(r for r in impact.impacted if r.node_id=="hospital")
    assert hospital.path==["camera","telecom","core","city","hospital"]
    assert hospital.score==80
    assert len(impact.critical_services)==6
    assert calculate_impact(twin,"hospital",.96).score==0


def test_isolation_prevents_all_propagation():
    twin=build_topology()
    isolate(twin,"camera")
    assert calculate_impact(twin,"camera",.96).impacted==[]
    assert continuity_verified(twin)


def test_protection_and_severity_reduce_risk():
    twin=build_topology()
    initial=calculate_impact(twin,"camera",.96)
    low=calculate_impact(twin,"camera",.4)
    assert low.score<initial.score
    protect(twin,initial.critical_services)
    assert calculate_impact(twin,"camera",.96).score<initial.score


def test_disconnected_graph_and_management_edges_do_not_propagate():
    twin=build_topology()
    for edge in twin.edges:
        if edge.source=="camera": edge.enabled=False
    assert calculate_impact(twin,"camera",1).score==0
    assert calculate_impact(twin,"guardian",1).impacted==[]


def test_cycles_terminate_and_maximum_risk_path_wins():
    twin=build_topology()
    twin.edges.append(Link(id="cycle",source="city",target="telecom"))
    twin.edges.append(Link(id="short-untrusted",source="camera",target="hospital",weight=.1))
    impact=calculate_impact(twin,"camera",.96)
    hospital=next(r for r in impact.impacted if r.node_id=="hospital")
    assert hospital.distance==4  # Longer but more exposed route beats the short low-weight route.
    assert len(impact.impacted)<=13


@pytest.mark.parametrize("score,band",[(0,"LOW"),(29,"LOW"),(30,"MODERATE"),(59,"MODERATE"),(60,"HIGH"),(79,"HIGH"),(80,"CRITICAL"),(100,"CRITICAL")])
def test_risk_bands(score,band):
    assert risk_band(score)==band


@pytest.mark.parametrize("scenario,technique",[("camera","T1210"),("identity","T1451"),("energy","T1489")])
def test_sentinel_evidence_and_mitre_mapping(scenario,technique):
    result=SentinelAgent().inspect(incident_for(scenario))
    assert result.techniques[0].id==technique
    assert len(result.evidence)==3
    assert result.reasoning
    assert result.source==SCENARIOS[scenario].source


@pytest.mark.parametrize("telemetry",[Telemetry(),Telemetry(remote_sessions=48),Telemetry(sim_swap_minutes_ago=12),Telemetry(service_stop_requests=26)])
def test_sentinel_does_not_classify_benign_or_insufficient_evidence(telemetry):
    incident=incident_for()
    incident.telemetry=telemetry
    with pytest.raises(ValueError,match="explicit threat rule"):
        SentinelAgent().inspect(incident)


def test_sentinel_uses_observations_instead_of_scenario_label():
    incident=incident_for("camera")
    incident.scenario_id="energy"
    incident.telemetry.remote_sessions=64
    classification=SentinelAgent().inspect(incident)
    assert classification.techniques[0].id=="T1210"
    assert "64" in classification.evidence[0]


def test_response_orders_protection_before_containment():
    incident=planned()
    kinds=[a.kind for a in incident.plan.actions]
    assert kinds.index("reroute")<kinds.index("quarantine")
    assert kinds.count("reroute")==6
    assert ComplianceAgent().validate(incident).decision=="APPROVED"


def test_shared_segment_requires_approval_and_fallback_is_safe():
    incident=planned("energy")
    assert ComplianceAgent().validate(incident).decision=="APPROVAL_REQUIRED"
    incident.plan=ResponseAgent().plan(incident,fallback=True)
    assert incident.plan.version==2
    assert all(a.kind!="isolate_segment" for a in incident.plan.actions)
    assert ComplianceAgent().validate(incident).decision=="APPROVED"


def test_critical_isolation_and_live_provider_are_hard_rejections():
    incident=planned()
    assert ComplianceAgent().validate(incident,simulated=False).decision=="REJECTED"
    incident.plan.actions[-1].target="hospital"
    assert ComplianceAgent().validate(incident).decision=="REJECTED"


def test_verb_cannot_bypass_shared_scope_approval():
    incident=planned()
    incident.plan.actions[-1].target="city"
    assert ComplianceAgent().validate(incident).decision=="APPROVAL_REQUIRED"


def test_isolation_before_service_protection_is_rejected():
    incident=planned("energy")
    segment=next(a for a in incident.plan.actions if a.kind=="isolate_segment")
    incident.plan.actions.remove(segment)
    incident.plan.actions.insert(0,segment)
    assert ComplianceAgent().validate(incident).decision=="REJECTED"


@pytest.mark.parametrize("node_id,state",[("city",None),("core",None),("hospital",SecurityState.OFFLINE),("hospital",SecurityState.ISOLATED)])
def test_continuity_rejects_failed_infrastructure(node_id,state):
    twin=build_topology()
    if state: asset(twin,node_id).state=state
    else: asset(twin,node_id).operational=False
    assert not continuity_verified(twin)


def test_protected_bypass_preserves_continuity():
    twin=build_topology()
    protect(twin,[n.id for n in twin.nodes if n.critical])
    isolate(twin,"city")
    assert continuity_verified(twin)


async def test_provider_is_deterministic_idempotent_and_simulated():
    provider=SimulatedNetworkProvider()
    incident=planned("identity")
    action=next(a for a in incident.plan.actions if a.kind=="sim_swap")
    first=await provider.execute(action,incident)
    assert first==await provider.execute(action,incident)
    assert first["simulated"] and first["swapped_in_24h"] and first["derived_risk"]=="HIGH"
    location=await provider.execute(incident.plan.actions[0],incident)
    assert location["verification"]=="FALSE"


async def test_provider_rejects_critical_target_and_arbitrary_endpoint():
    provider=SimulatedNetworkProvider()
    incident=planned()
    action=incident.plan.actions[-1].model_copy(deep=True)
    action.target="hospital"
    with pytest.raises(ValueError): await provider.execute(action,incident)
    action.target="camera"
    action.endpoint="https://example.com/execute"
    with pytest.raises(ValueError): await provider.execute(action,incident)


def test_payload_validation():
    with pytest.raises(ValidationError): StartRequest(step_duration=-1)
    with pytest.raises(ValidationError): StartRequest(mode="unknown")
    with pytest.raises(ValidationError): StartRequest(arbitrary_command="invalid")
    with pytest.raises(ValidationError): Action(id="x",kind="shell",target="camera",endpoint="/exec",rationale="",expected_effect="")
