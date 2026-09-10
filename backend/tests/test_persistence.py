from datetime import datetime, timedelta, timezone
from app.models import Incident
from app.agents import initial_agents
from app.topology import build_topology


def test_history_limits_by_time_and_recovers_all_unfinished_records(repository):
    base=datetime(2026,1,1,tzinfo=timezone.utc)
    for index in range(102):
        incident=Incident(id=f"GM-{102-index:03}",scenario_id="camera",title="History test",source="camera",mode="fast",
                          auto_approve=True,step_duration=.01,topology=build_topology(),agents=initial_agents(),
                          started_at=(base+timedelta(seconds=index)).isoformat(),status="RUNNING" if index in (0,101) else "RESET")
        repository.save(incident)
    history=repository.list()
    assert len(history)==100
    assert history[0].id=="GM-001"
    assert history[-1].id=="GM-100"
    repository.recover()
    assert repository.get("GM-102").status=="INTERRUPTED"
    assert repository.get("GM-001").status=="INTERRUPTED"
