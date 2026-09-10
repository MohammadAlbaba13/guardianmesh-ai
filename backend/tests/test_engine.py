import asyncio
import pytest
from app.models import StartRequest, ApprovalRequest
from app.engine import Conflict, SimulationEngine
from app.topology import asset, online_services, continuity_verified


async def wait_until(predicate, timeout=8):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.005)


@pytest.mark.parametrize("scenario",["camera","identity","energy"])
async def test_full_scenario_all_agents_actions_reports_and_reset(engine,scenario):
    incident=await engine.start(scenario,StartRequest(step_duration=.01))
    await asyncio.wait_for(engine.task,10)
    assert incident.status=="CONTAINED", incident.outcome
    assert incident.phase=="COMPLETE"
    assert all(a.state=="COMPLETE" for a in incident.agents)
    assert all(a.status=="COMPLETE" and a.result["simulated"] for a in incident.actions)
    assert asset(incident.topology,incident.source).state=="ISOLATED"
    assert incident.residual_impact.score==0
    assert continuity_verified(incident.topology)
    assert all(s.online==6 for s in incident.samples)
    assert incident.report.technical["timeline"]==[e.model_dump() for e in incident.timeline]
    assert incident.report.executive["actions_completed"]==len(incident.actions)
    assert incident.report.technical["source_asset"]["state"]=="ISOLATED"
    restored=engine.repository.get(incident.id)
    assert restored.report==incident.report
    assert [e.seq for e in incident.timeline]==list(range(1,len(incident.timeline)+1))
    if scenario=="energy": assert incident.approvals[0].actor=="DEMO_AUTOMATION"
    await engine.control(incident.id,"reset")
    assert all(n.state=="ONLINE" for n in incident.topology.nodes)
    assert online_services(incident.topology)==6
    assert incident.report.technical["source_asset"]["state"]=="ISOLATED"  # Historical report is immutable.


async def test_repeat_runs_have_identical_findings_and_actions(engine):
    runs=[]
    for _ in range(2):
        incident=await engine.start("camera",StartRequest(step_duration=.01))
        await engine.task
        runs.append((incident.classification.model_dump(),incident.impact.model_dump(),[(a.kind,a.target,a.result) for a in incident.actions],[e.type for e in incident.timeline],incident.outcome))
    assert runs[0]==runs[1]


@pytest.mark.parametrize("decision",["APPROVE","REJECT"])
async def test_manual_approval_and_rejection(engine,decision):
    incident=await engine.start("energy",StartRequest(step_duration=.01,auto_approve=False))
    await wait_until(lambda:incident.status=="AWAITING_APPROVAL")
    seq=len(incident.timeline)
    await asyncio.sleep(.08)
    assert len(incident.timeline)==seq and incident.actions==[]
    with pytest.raises(Conflict): await engine.control(incident.id,"skip")
    with pytest.raises(Conflict): await engine.approve(incident.id,ApprovalRequest(plan_id="stale",plan_version=1,decision=decision))
    payload=ApprovalRequest(plan_id=incident.plan.id,plan_version=1,decision=decision)
    await engine.approve(incident.id,payload)
    with pytest.raises(Conflict): await engine.approve(incident.id,payload)
    await asyncio.wait_for(engine.task,10)
    assert incident.status=="CONTAINED"
    assert incident.approvals[0].actor=="OPERATOR"
    assert any(a.kind=="isolate_segment" for a in incident.actions)==(decision=="APPROVE")
    assert incident.plan.version==(1 if decision=="APPROVE" else 2)
    assert [p.version for p in incident.plan_history]==([1] if decision=="APPROVE" else [1,2])
    assert incident.report.technical["plan_history"][0]["actions"]
    assert incident.report.technical["policy_history"][0]["result"]["decision"]=="APPROVAL_REQUIRED"


async def test_pause_resume_skip_and_overlap(engine):
    incident=await engine.start("camera",StartRequest(mode="guided",step_duration=.08))
    await engine.control(incident.id,"pause")
    seq=len(incident.timeline)
    await asyncio.sleep(.15)
    assert len(incident.timeline)==seq
    with pytest.raises(Conflict): await engine.start("identity",StartRequest())
    await engine.control(incident.id,"resume")
    await engine.control(incident.id,"skip")
    await asyncio.wait_for(engine.task,10)
    ids=[a.id for a in incident.actions]
    assert len(ids)==len(set(ids)) and incident.status=="CONTAINED"


async def test_reset_cancels_wait_and_next_run_is_clean(engine):
    incident=await engine.start("energy",StartRequest(auto_approve=False,step_duration=.01))
    await wait_until(lambda:incident.status=="AWAITING_APPROVAL")
    await engine.control(incident.id,"reset")
    seq=len(incident.timeline)
    await asyncio.sleep(.05)
    assert len(incident.timeline)==seq and engine.task.cancelled()
    next_run=await engine.start("identity",StartRequest(step_duration=.01))
    await engine.task
    assert next_run.status=="CONTAINED" and next_run.approvals==[]


@pytest.mark.parametrize("waiting",["pause","approval"])
async def test_historical_reset_cannot_change_current_gates(engine,waiting):
    old=await engine.start("camera",StartRequest(step_duration=.01))
    await engine.task
    new=await engine.start("energy",StartRequest(auto_approve=False,step_duration=.01))
    if waiting=="pause": await engine.control(new.id,"pause")
    else: await wait_until(lambda:new.status=="AWAITING_APPROVAL")
    seq=len(new.timeline)
    await engine.control(old.id,"reset")
    await asyncio.sleep(.1)
    assert len(new.timeline)==seq
    assert new.status==("PAUSED" if waiting=="pause" else "AWAITING_APPROVAL")


async def test_provider_failure_never_claims_containment(repository):
    class FailingProvider:
        simulated=True
        async def execute(self,*args): raise RuntimeError("Injected provider failure")
    engine=SimulationEngine(repository,FailingProvider())
    incident=await engine.start("camera",StartRequest(step_duration=.01))
    await engine.task
    assert incident.status=="FAILED" and incident.report is None
    assert incident.actions[0].status=="FAILED"
    assert not any(e.type=="INCIDENT_CONTAINED" for e in incident.timeline)


async def test_reset_during_provider_call_prevents_stale_mutation(repository):
    entered=asyncio.Event()
    class SlowProvider:
        simulated=True
        async def execute(self,*args):
            entered.set()
            await asyncio.Event().wait()
    engine=SimulationEngine(repository,SlowProvider())
    incident=await engine.start("camera",StartRequest(step_duration=.01))
    await asyncio.wait_for(entered.wait(),5)
    await engine.control(incident.id,"reset")
    assert incident.status=="RESET" and all(n.state=="ONLINE" for n in incident.topology.nodes)
    assert all(a.status!="COMPLETE" for a in incident.actions)


async def test_reconnect_snapshot_and_backpressure_preserve_full_timeline(engine):
    incident=await engine.start("camera",StartRequest(step_duration=.01))
    queue=engine.subscribe(incident.id)
    first=await queue.get()
    assert first["seq"]>=1
    await engine.task
    latest=None
    while not queue.empty(): latest=queue.get_nowait()
    assert latest["incident"]["report"]
    assert len(latest["incident"]["timeline"])==len(incident.timeline)
    engine.unsubscribe(incident.id,queue)
    reconnect=engine.subscribe(incident.id)
    assert (await reconnect.get())["incident"]["status"]=="CONTAINED"


async def test_recovery_marks_running_state_interrupted(repository):
    engine=SimulationEngine(repository)
    incident=await engine.start("camera",StartRequest(step_duration=1))
    await engine.close()
    repository.recover()
    assert repository.get(incident.id).status=="INTERRUPTED"


async def test_manual_rejection_wins_auto_approval_timer_race(engine,monkeypatch):
    original_approve=engine.approve
    async def racing_approve(incident_id,request,actor="OPERATOR"):
        if actor=="DEMO_AUTOMATION":
            await original_approve(incident_id,request.model_copy(update={"decision":"REJECT"}),"OPERATOR")
        return await original_approve(incident_id,request,actor)
    monkeypatch.setattr(engine,"approve",racing_approve)
    incident=await engine.start("energy",StartRequest(step_duration=.01))
    await engine.task
    assert incident.status=="CONTAINED"
    assert len(incident.approvals)==1
    assert incident.approvals[0].decision=="REJECT"
    assert incident.approvals[0].actor=="OPERATOR"
    assert not any(a.kind=="isolate_segment" for a in incident.actions)


async def test_abrupt_restart_recovers_contained_report(engine,repository):
    incident=await engine.start("camera",StartRequest(step_duration=.01))
    await engine.task
    incident.report=None
    incident.phase="CONTAINED"
    incident.timeline=[e for e in incident.timeline if e.type!="REPORT_GENERATED"]
    incident.agents[-1].state="ANALYZING"
    repository.save(incident)
    repository.recover()
    recovered=repository.get(incident.id)
    assert recovered.status=="CONTAINED" and recovered.phase=="COMPLETE"
    assert recovered.report and recovered.report.technical["timeline"][-1]["type"]=="REPORT_GENERATED"
    assert recovered.agents[-1].state=="COMPLETE"


async def test_orderly_shutdown_finishes_verified_containment_report(engine):
    incident=await engine.start("camera",StartRequest(step_duration=.03))
    await wait_until(lambda:incident.status=="CONTAINED")
    await engine.close()
    assert incident.status=="CONTAINED" and incident.report
    assert incident.phase=="COMPLETE"
