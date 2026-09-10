import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'api.db'}")) as value:
        yield value


def test_health_topology_catalog_and_input_guards(client):
    assert client.get("/api/health").json()["simulation"] is True
    assert len(client.get("/api/topology").json()["nodes"])==14
    assert len(client.get("/api/scenarios").json())==3
    assert client.post("/api/scenarios/unknown/start",json={}).status_code==404
    assert client.post("/api/scenarios/camera/start",json={"step_duration":-1}).status_code==422
    assert client.post("/api/scenarios/camera/start",json={},headers={"Origin":"https://untrusted.example"}).status_code==403
    assert client.get("/api/incidents/missing").status_code==404


def test_websocket_lifecycle_and_persisted_report(client):
    response=client.post("/api/scenarios/camera/start",json={"step_duration":.01})
    assert response.status_code==201
    incident_id=response.json()["id"]
    assert client.get(f"/api/incidents/{incident_id}/report").status_code==409
    assert client.post("/api/scenarios/identity/start",json={}).status_code==409
    with client.websocket_connect(f"/ws/incidents/{incident_id}") as socket:
        snapshot=socket.receive_json()
        assert snapshot["type"]=="SNAPSHOT"
        while snapshot["incident"]["phase"]!="COMPLETE": snapshot=socket.receive_json()
        assert snapshot["incident"]["status"]=="CONTAINED"
        assert len(snapshot["incident"]["agents"])==6
    report=client.get(f"/api/incidents/{incident_id}/report").json()
    assert report["executive"]["minimum_services_online"]==6
    assert report["technical"]["timeline"][-1]["type"]=="REPORT_GENERATED"
    export=client.get(f"/api/incidents/{incident_id}/report?download=true")
    assert export.status_code==200 and export.json()==report
    assert export.headers["content-disposition"]==f'attachment; filename="{incident_id}-incident-report.json"'
    assert client.get("/api/incidents").json()[0]["has_report"]
    with client.websocket_connect(f"/ws/incidents/{incident_id}") as socket:
        assert socket.receive_json()["incident"]["report"]==report
        socket.send_text("ping")
        assert socket.receive_json()["type"]=="PONG"
    assert client.post(f"/api/incidents/{incident_id}/reset",json={}).json()["status"]=="RESET"


def test_api_manual_rejection_completes_without_segment_action(client):
    incident_id=client.post("/api/scenarios/energy/start",json={"step_duration":.01,"auto_approve":False}).json()["id"]
    with client.websocket_connect(f"/ws/incidents/{incident_id}") as socket:
        snapshot=socket.receive_json()
        while snapshot["incident"]["status"]!="AWAITING_APPROVAL": snapshot=socket.receive_json()
        plan=snapshot["incident"]["plan"]
        assert client.post(f"/api/incidents/{incident_id}/skip",json={}).status_code==409
        response=client.post(f"/api/incidents/{incident_id}/approval",json={"plan_id":plan["id"],"plan_version":1,"decision":"REJECT"})
        assert response.status_code==200
        while snapshot["incident"]["phase"]!="COMPLETE": snapshot=socket.receive_json()
        assert all(a["kind"]!="isolate_segment" for a in snapshot["incident"]["actions"])
        assert snapshot["incident"]["status"]=="CONTAINED"


@pytest.mark.parametrize("binary",[False,True])
def test_malformed_websocket_messages_are_rejected_and_cleaned(client,binary):
    incident_id=client.post("/api/scenarios/camera/start",json={"step_duration":1}).json()["id"]
    with client.websocket_connect(f"/ws/incidents/{incident_id}") as socket:
        socket.receive_json()
        if binary: socket.send_bytes(b"invalid")
        else: socket.send_text('{"command":"execute"}')
        with pytest.raises(WebSocketDisconnect) as error: socket.receive_json()
        assert error.value.code==1008
    assert not client.app.state.engine.subscribers.get(incident_id)


def test_websocket_origin_and_unknown_incident_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/incidents/unknown'): pass
    incident_id=client.post('/api/scenarios/camera/start',json={"step_duration":1}).json()["id"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f'/ws/incidents/{incident_id}',headers={"Origin":"https://untrusted.example"}): pass
