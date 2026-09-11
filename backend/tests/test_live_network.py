import asyncio
import json
import httpx
import pytest
from app.providers.qod import QoDConfig, QoDClient, NetworkError
from app.providers.service import NetworkActionService
from app.models import StartRequest, ApprovalRequest
from app.engine import SimulationEngine, Conflict
from app.persistence import Repository
from test_providers import sample_incident, action


def config(**updates):
    return QoDConfig(api_key="test-secret-never-output", authorized=True, bindings={"hospital": {
        "device": {"phoneNumber": "+999991234567"}, "applicationServer": {"ipv4Address": "233.252.0.2"},
        "qosProfile": "QOS_E", "duration": 300}}, **updates)


def transport(calls, status=201, body=None):
    def handle(request):
        calls.append(request)
        if request.method == "DELETE": return httpx.Response(204)
        return httpx.Response(status if request.method == "POST" else 200,
            json=body if body is not None else {"sessionId": "sandbox-session-1", "qosStatus": "AVAILABLE", "token": "must-not-persist"})
    return httpx.MockTransport(handle)


async def test_qod_create_lookup_delete_extend_and_sanitized_wire_contract():
    calls=[]; client=QoDClient(config(), transport(calls))
    session,status=await client.create(config().bindings['hospital'])
    assert status==201 and session.sessionId=='sandbox-session-1'
    await client.get(session.sessionId); await client.extend(session.sessionId,300); await client.delete(session.sessionId)
    assert [r.method for r in calls]==['POST','GET','POST','DELETE']
    assert calls[0].url.path=='/quality-on-demand/v1/sessions'
    assert calls[0].headers['X-RapidAPI-Host']=='network-as-code.nokia.rapidapi.com'
    assert json.loads(calls[0].content)['qosProfile']=='QOS_E'
    assert json.loads(calls[2].content)=={'requestedAdditionalDuration':300}
    assert 'token' not in session.model_dump()
    assert 'test-secret' not in repr(config())


@pytest.mark.parametrize('status,code',[(401,'AUTH_FAILED'),(403,'AUTH_FAILED'),(429,'RATE_LIMITED'),(500,'PROVIDER_ERROR'),(302,'PROVIDER_ERROR')])
async def test_http_failures_redacted_and_post_never_retried(status,code):
    calls=[];client=QoDClient(config(),transport(calls,status,{'password':'provider-secret'}))
    with pytest.raises(NetworkError,match=code) as exc: await client.create(config().bindings['hospital'])
    assert exc.value.status==status and len(calls)==1 and 'secret' not in str(exc.value)


@pytest.mark.parametrize('body',[{},[],{'sessionId':'s','qosStatus':'FAKE'},{'sessionId':'../../escape','qosStatus':'AVAILABLE'},{'sessionId':'s'}])
async def test_malformed_responses_never_claim_live_success(body):
    with pytest.raises(NetworkError,match='MALFORMED_RESPONSE'):
        await QoDClient(config(),transport([],body=body)).create(config().bindings['hospital'])


async def test_timeout_unknown_never_falls_back_or_retries():
    calls=[]
    def fail(r): calls.append(r);raise httpx.ReadTimeout('secret-url')
    provider=NetworkActionService('AUTO',True,config=config(),transport=httpx.MockTransport(fail))
    a=action('qod','hospital');i=sample_incident()
    with pytest.raises(NetworkError,match='TIMEOUT_OUTCOME_UNKNOWN'):await provider.execute(a,i)
    assert len(calls)==1 and a.result['execution_state']=='LIVE_FAILED' and not a.result['fallback']
    assert 'secret-url' not in json.dumps(a.result)
    with pytest.raises(NetworkError,match='DUPLICATE'):await provider.execute(a,i)
    assert len(calls)==1


async def test_auto_fallback_explicit_and_live_fail_closed():
    i=sample_incident();a=action('qod','device')
    provider=NetworkActionService('AUTO',True,config=QoDConfig())
    result=await provider.execute(a,i)
    assert result['mode']=='SIMULATED' and result['execution_state']=='FALLBACK_SIMULATED' and result['live_error']=='LIVE_PROVIDER_UNCONFIGURED'
    with pytest.raises(NetworkError):await NetworkActionService('LIVE',True,config=QoDConfig()).execute(action('qod'),i)


async def test_requested_session_is_not_verified_and_retains_cleanup_id():
    provider=NetworkActionService('AUTO',True,config=config(poll_attempts=1),transport=transport([],body={'sessionId':'pending','qosStatus':'REQUESTED'}))
    a=action('qod','hospital')
    with pytest.raises(NetworkError,match='VERIFICATION_PENDING'):await provider.execute(a,sample_incident())
    assert a.result['external_session_id']=='pending' and a.result['verification']=='NOT_VERIFIED' and a.result['fallback'] is False


async def wait_phase(engine, phase):
    async with asyncio.timeout(10):
        while engine.current.phase!=phase:
            if engine.task.done(): raise AssertionError(engine.current.outcome)
            await asyncio.sleep(.01)


async def test_hero_approval_once_persistence_live_proof_and_reset_cleanup(tmp_path):
    calls=[];repo=Repository(f'sqlite:///{tmp_path / "live.db"}')
    provider=NetworkActionService('LIVE',config=config(),transport=transport(calls))
    engine=SimulationEngine(repo,provider=provider)
    i=await engine.start('camera',StartRequest(step_duration=.01,execution_mode='LIVE',auto_approve=False,manual_approval=True))
    await wait_phase(engine,'APPROVAL');assert calls==[]
    req=ApprovalRequest(plan_id=i.plan.id,plan_version=1,decision='APPROVE')
    await engine.approve(i.id,req)
    with pytest.raises(Conflict):await engine.approve(i.id,req)
    await engine.task
    assert i.status=='CONTAINED' and i.residual_impact.score==0
    assert len([r for r in calls if r.method=='POST'])==1
    live=next(a for a in i.actions if a.result.get('mode')=='LIVE')
    assert live.result['verification']=='VERIFIED'
    assert next(n for n in i.topology.nodes if n.id=='hospital').latency_ms==45
    saved=repo.get(i.id)
    assert saved.actions==i.actions and saved.report.technical['network_actions']
    assert any(e.type=='NETWORK_VERIFIED' for e in saved.timeline)
    assert 'test-secret' not in saved.model_dump_json() and 'must-not-persist' not in saved.model_dump_json()
    await engine.control(i.id,'reset')
    assert calls[-1].method=='DELETE' and live.result['cleanup']=='DELETED'
    assert next(a for a in repo.get(i.id).report.technical['network_actions'] if a['result'].get('mode')=='LIVE')['result']['cleanup']=='DELETED'
    await engine.close();repo.engine.dispose()


async def test_rejected_approval_no_network_or_local_action(tmp_path):
    calls=[];repo=Repository(f'sqlite:///{tmp_path / "reject.db"}')
    engine=SimulationEngine(repo,provider=NetworkActionService('LIVE',config=config(),transport=transport(calls)))
    i=await engine.start('camera',StartRequest(step_duration=.01,execution_mode='LIVE',auto_approve=False))
    await wait_phase(engine,'APPROVAL')
    await engine.approve(i.id,ApprovalRequest(plan_id=i.plan.id,plan_version=1,decision='REJECT'))
    await engine.task
    assert calls==[] and i.actions==[] and i.status=='FAILED' and i.report
    await engine.close();repo.engine.dispose()


async def test_blocked_plan_never_invokes_provider(tmp_path,monkeypatch):
    from app.agents import ResponseAgent
    original=ResponseAgent.plan
    def unsafe(self,incident,fallback=False):
        plan=original(self,incident,fallback)
        plan.actions[-1].target='hospital'
        return plan
    monkeypatch.setattr(ResponseAgent,'plan',unsafe)
    calls=[];repo=Repository(f'sqlite:///{tmp_path / "blocked.db"}')
    engine=SimulationEngine(repo,provider=NetworkActionService('LIVE',config=config(),transport=transport(calls)))
    i=await engine.start('camera',StartRequest(step_duration=.01,execution_mode='LIVE'))
    await engine.task
    assert calls==[] and i.actions==[] and i.policy.decision=='REJECTED'
    await engine.close();repo.engine.dispose()


@pytest.mark.parametrize('url',['http://example.com/v1/sessions','https://127.0.0.1/v1/sessions','https://u:p@example.com/v1/sessions','https://example.com/v2/sessions'])
def test_unsafe_or_unreviewed_urls_rejected(url):
    with pytest.raises(ValueError):QoDConfig(provider='camara',sessions_url=url)


async def test_async_delete_acceptance_is_not_fabricated_as_completed():
    client=QoDClient(config(),httpx.MockTransport(lambda r:httpx.Response(202)))
    with pytest.raises(NetworkError,match='DELETE_NOT_CONFIRMED'):await client.delete('known-session')


@pytest.mark.parametrize('mode,manual', [('LIVE', False), ('AUTO', False), ('SIMULATION', True)])
async def test_demo_automation_cannot_override_operator_gate(tmp_path, mode, manual):
    calls = []
    repo = Repository(f'sqlite:///{tmp_path / "gate.db"}')
    from app.providers.simulated import SimulatedNetworkProvider
    provider = SimulatedNetworkProvider() if mode == 'SIMULATION' else NetworkActionService(mode, config=config(), transport=transport(calls))
    engine = SimulationEngine(repo, provider=provider)
    try:
        incident = await engine.start('camera', StartRequest(step_duration=.01,
            execution_mode=mode, manual_approval=manual, auto_approve=True))
        await wait_phase(engine, 'APPROVAL')
        await asyncio.sleep(.15)
        assert incident.status == 'AWAITING_APPROVAL'
        assert incident.approvals == [] and calls == []
    finally:
        await engine.close()
        repo.engine.dispose()


async def test_deleted_session_clears_current_verification():
    provider = NetworkActionService('LIVE', config=config(), transport=transport([]))
    incident = sample_incident()
    planned = action('qod', 'hospital')
    planned.result = await provider.execute(planned, incident)
    await provider.manage(planned, incident, 'delete')
    assert planned.result['verification'] == 'NOT_VERIFIED'
    assert planned.result['execution_state'] == 'ENDED'
