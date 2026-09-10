import pytest
from pydantic import ValidationError
from app.models import Action, Asset, Incident, Link, Signal, SignalTelemetry, Topology, Telemetry
from app.capabilities import get_capability, list_capabilities
from app.providers import SimulatedNetworkProvider, select_provider, CamaraNetworkProvider, NokiaNetworkProvider, ProviderUnavailable, CapabilityResult
from app.providers.camara import SandboxBinding


def sample_incident():
    nodes = [Asset(id=id, name=id, kind=kind, zone="demo", critical=critical, criticality=.9,
                   exposure=.8, x=x, y=0) for id, kind, critical, x in
             [("device", "device", False, 0), ("core", "core", False, 100), ("edge", "edge", False, 200), ("service", "service", True, 300)]]
    return Incident(id="provider-test", scenario_id="test", title="Test", source="device", mode="fast",
        auto_approve=True, step_duration=.01, agents=[], topology=Topology(nodes=nodes, edges=[
            Link(id="a", source="device", target="core"), Link(id="b", source="core", target="edge"),
            Link(id="c", source="edge", target="service")]),
        telemetry=SignalTelemetry(signals=[Signal(id="sim_swap_minutes_ago",value=8), Signal(id="location_matches",value=False),
            Signal(id="device_changed",value=True),Signal(id="number_verified",value=False),Signal(id="device_reachable",value=True)]))


def action(kind, target="device", id=None):
    return Action(id=id or kind, kind=kind, target=target, endpoint=get_capability(kind).endpoint,
                  rationale="Test observed capability", expected_effect="Local evidence")


@pytest.mark.parametrize("capability", [c.id for c in list_capabilities()])
async def test_all_capabilities_validate_truthful_envelope(capability):
    incident = sample_incident()
    before = incident.model_dump()
    result = await SimulatedNetworkProvider().execute(action(capability), incident)
    envelope = CapabilityResult.model_validate({k: result[k] for k in CapabilityResult.model_fields})
    assert envelope.mode == "SIMULATED" and envelope.simulated and envelope.capability == capability
    assert envelope.summary and envelope.evidence
    assert incident.model_dump() == before  # Provider cannot bypass core topology mutation.
    assert all(result[key] == value for key, value in envelope.evidence.items())


async def test_provider_idempotence_and_argument_conflict():
    provider, incident = SimulatedNetworkProvider(), sample_incident()
    first = await provider.execute(action("qod"), incident)
    first["evidence"]["latency_after_ms"] = 900
    incident.topology.nodes[0].latency_ms = 100
    repeated = await provider.execute(action("qod"), incident)
    assert repeated["latency_before_ms"] == 45 and repeated["evidence"]["latency_after_ms"] == 8
    with pytest.raises(ValueError, match="Idempotency"):
        await provider.execute(action("qod", "edge"), incident)


@pytest.mark.parametrize("kind", ["quarantine", "isolate_segment", "restrict_session"])
async def test_provider_rejects_critical_restriction(kind):
    with pytest.raises(ValueError, match="Critical-service"):
        await SimulatedNetworkProvider().execute(action(kind, "service"), sample_incident())


async def test_provider_rejects_unknown_target_and_mismatched_endpoint():
    provider, incident = SimulatedNetworkProvider(), sample_incident()
    with pytest.raises(ValueError, match="target"):
        await provider.execute(action("qod", "absent"), incident)
    bad = action("qod").model_copy(update={"endpoint": "https://untrusted.example/action"})
    with pytest.raises(ValueError, match="registry"):
        await provider.execute(bad, incident)


async def test_signal_evidence_and_sim_change_alone_not_compromise():
    incident = sample_incident()
    provider = SimulatedNetworkProvider()
    assert (await provider.execute(action("sim_swap"), incident))["derived_risk"] == "HIGH"
    assert (await provider.execute(action("number_verify"), incident))["verified"] is False
    assert (await provider.execute(action("step_up"), incident))["verified"] is False
    incident.telemetry = Telemetry(sim_swap_minutes_ago=8)
    assert (await SimulatedNetworkProvider().execute(action("sim_swap"), incident))["derived_risk"] == "LOW"


async def test_edge_discovery_follows_enabled_paths():
    incident = sample_incident()
    assert (await SimulatedNetworkProvider().execute(action("edge_discovery"), incident))["edge_id"] == "edge"
    incident.topology.edges[1].enabled = False
    assert (await SimulatedNetworkProvider().execute(action("edge_discovery"), incident))["edge_id"] is None


@pytest.mark.parametrize("name", ["camara", "nokia", "unknown"])
def test_requested_external_provider_remains_explicit_simulation(monkeypatch, name):
    monkeypatch.setenv("GUARDIANMESH_NETWORK_PROVIDER", name)
    provider = select_provider()
    assert provider.simulated and provider.mode == "SIMULATED" and provider.requested_mode == name
    assert provider.notice and "SIMULATED" in provider.notice


@pytest.mark.parametrize("provider", [CamaraNetworkProvider, NokiaNetworkProvider])
async def test_unbound_sandbox_never_claims_execution(provider):
    with pytest.raises(ProviderUnavailable, match="authorized"):
        await provider().execute(action("qod"), sample_incident())
    with pytest.raises(ProviderUnavailable, match="Conceptual"):
        await provider().execute(action("quarantine"), sample_incident())


async def test_authorized_binding_still_requires_installed_transport():
    binding = SandboxBinding(provider="camara",base_url="https://operator.example",token="placeholder",
        authorized=True,api_version="review-required",capabilities=["qod"],device_bindings={"device":"synthetic-binding"})
    with pytest.raises(ProviderUnavailable,match="transport"):
        await CamaraNetworkProvider(binding).execute(action("qod"),sample_incident())
    assert "placeholder" not in repr(binding)
    with pytest.raises(ValidationError):
        binding.model_validate({**binding.model_dump(),"capabilities":["quarantine"]})


def test_registry_unique_and_truthful_mode_validation():
    assert len(list_capabilities()) == len({c.id for c in list_capabilities()}) == 13
    with pytest.raises(ValueError): get_capability("made_up")
    with pytest.raises(ValidationError):
        CapabilityResult(provider="bad",mode="LIVE",simulated=True,capability="qod",summary="bad",evidence={})
