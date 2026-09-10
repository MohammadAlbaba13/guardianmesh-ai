import asyncio
import json
import pytest
import httpx
from app.models import Classification, Impact
from app.intelligence import choose_reasoner, DeterministicReasoner, LocalLLMReasoner
from test_providers import sample_incident


def incident():
    value = sample_incident()
    value.classification = Classification(threat_type="Observed anomaly", confidence=.9,source=value.source,
        evidence=["Recent SIM change and location mismatch"],reasoning="Correlated trust signals",techniques=[])
    value.impact = Impact(score=70,explanation="Reachable critical service at risk")
    return value


def valid_output():
    return dict(interpretation="Correlated trust anomaly",risk_rationale="A critical dependency is reachable",
        priorities=["service"],action_rationale=["Preserve service and restrict only affected context"],evidence_refs=["evidence:0","impact"])


async def test_deterministic_reasoner_uses_actual_evidence_without_mutation():
    value = incident()
    before = value.model_dump()
    result = await DeterministicReasoner().reason(value,("qod",))
    assert result.mode == "deterministic" and result.interpretation == value.classification.reasoning
    assert result.risk_rationale == value.impact.explanation and result.priorities == ["service"]
    assert result.evidence_refs == ["evidence:0","impact"] and value.model_dump() == before


async def test_valid_ollama_advisory_is_structured_and_has_no_action_authority():
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={"done":True,"response":json.dumps(valid_output())})
    value = incident()
    before = value.model_dump()
    reasoner = LocalLLMReasoner("http://127.0.0.1:11434","installed-local-model",transport=httpx.MockTransport(respond))
    result = await reasoner.reason(value,("qod",))
    assert result.mode == "local_llm" and result.fallback_reason is None
    assert requests[0]["stream"] is False and requests[0]["format"]["additionalProperties"] is False
    assert "qod" in requests[0]["prompt"] and value.model_dump() == before and value.actions == []


@pytest.mark.parametrize("change", [
    {"priorities":["invented-service"]}, {"evidence_refs":["fake-evidence"]},
    {"actions":[{"kind":"isolate_segment"}]}, {"interpretation":"x"*1601},
    {"priorities":["service","service"]}, {"evidence_refs":[]}, {"interpretation":12},
])
async def test_invalid_advisory_falls_back_without_weakening_safety(change):
    output = {**valid_output(),**change}
    transport = httpx.MockTransport(lambda r:httpx.Response(200,json={"done":True,"response":json.dumps(output)}))
    result = await LocalLLMReasoner("http://localhost:11434","test",transport=transport).reason(incident(),("qod",))
    assert result.mode == "deterministic" and result.requested_mode == "local_llm" and result.fallback_reason


@pytest.mark.parametrize("body", ["not json", '{"done":false,"response":"{}"}', '{"done":true,"response":"not json"}', "x"*65537],
                         ids=["invalid-envelope", "incomplete", "invalid-output", "oversized"])
async def test_malformed_or_oversized_transport_falls_back(body):
    transport = httpx.MockTransport(lambda r:httpx.Response(200,text=body))
    result = await LocalLLMReasoner("http://localhost:11434","test",transport=transport).reason(incident(),())
    assert result.mode == "deterministic" and result.fallback_reason


async def test_unavailable_timeout_and_cancellation():
    def unavailable(request): raise httpx.ConnectError("private endpoint failure")
    reasoner = LocalLLMReasoner("http://localhost:11434","test",transport=httpx.MockTransport(unavailable))
    result = await reasoner.reason(incident(),())
    assert result.mode == "deterministic" and "private endpoint" not in result.fallback_reason
    async def slow(request):
        await asyncio.sleep(5)
        return httpx.Response(200,json={})
    reasoner = LocalLLMReasoner("http://localhost:11434","test",timeout=.01,transport=httpx.MockTransport(slow))
    assert (await reasoner.reason(incident(),())).mode == "deterministic"
    task = asyncio.create_task(LocalLLMReasoner("http://localhost:11434","test",transport=httpx.MockTransport(slow)).reason(incident(),()))
    await asyncio.sleep(.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task


@pytest.mark.parametrize("url", ["https://remote.example","http://localhost.evil","http://user:secret@localhost:11434","http://127.0.0.1/api","file:///tmp/model"])
def test_local_model_cannot_send_evidence_to_external_host(url):
    with pytest.raises(ValueError): LocalLLMReasoner(url,"test")


def test_configuration_fallback_and_default(monkeypatch):
    monkeypatch.delenv("GUARDIANMESH_REASONER",raising=False)
    assert choose_reasoner().mode == "deterministic"
    monkeypatch.setenv("GUARDIANMESH_REASONER","local_llm")
    monkeypatch.delenv("GUARDIANMESH_OLLAMA_MODEL",raising=False)
    result = choose_reasoner()
    assert result.mode == "deterministic" and result.requested_mode == "local_llm" and result.fallback_reason
    monkeypatch.setenv("GUARDIANMESH_OLLAMA_MODEL","test")
    assert choose_reasoner().mode == "local_llm"
    monkeypatch.setenv("GUARDIANMESH_OLLAMA_TIMEOUT","bad")
    assert choose_reasoner().mode == "deterministic"
