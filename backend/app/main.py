import asyncio
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from .engine import SimulationEngine, Conflict
from .models import StartRequest, ApprovalRequest
from .persistence import Repository
from .scenarios import scenario_catalog
from .topology import build_topology


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "message":record.getMessage(),
                           "incident_id":getattr(record, "incident_id", None), "event":getattr(record, "event_type", None),
                           "error":self.formatException(record.exc_info) if record.exc_info else None})


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.getLogger("guardianmesh").addHandler(handler)
logging.getLogger("guardianmesh").setLevel(logging.INFO)

ORIGINS = {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 8000, 8080)}


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = Repository(database_url)
        repository.recover()
        app.state.engine = SimulationEngine(repository)
        yield
        await app.state.engine.close()
        repository.engine.dispose()

    app = FastAPI(title="GuardianMesh AI", version="1.0.0", description="Local defensive simulation. No real telecom connectivity.", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=sorted(ORIGINS), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def restrict_origin(request: Request, call_next):
        if request.method != "GET" and request.headers.get("origin") and request.headers["origin"] not in ORIGINS:
            return JSONResponse({"detail":"Only the local command center may control this simulation."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse({"detail":str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing_handler(request, exc):
        return JSONResponse({"detail":"Unknown incident, scenario or control."}, status_code=404)

    @app.get("/api/health")
    async def health():
        return {"status":"ok", "simulation":True, "provider":"local", "agents":6, "critical_services":6}

    @app.get("/api/topology")
    async def topology():
        return build_topology()

    @app.get("/api/scenarios")
    async def scenarios():
        return scenario_catalog()

    @app.get("/api/incidents")
    async def incidents():
        return [{"id":i.id, "title":i.title, "status":i.status, "started_at":i.started_at, "has_report":bool(i.report)} for i in app.state.engine.repository.list()]

    @app.post("/api/scenarios/{scenario_id}/start", status_code=201)
    async def start(scenario_id: str, payload: StartRequest):
        return await app.state.engine.start(scenario_id, payload)

    @app.get("/api/incidents/{incident_id}")
    async def incident(incident_id: str):
        return app.state.engine.get(incident_id)

    @app.get("/api/incidents/{incident_id}/timeline")
    async def timeline(incident_id: str):
        return app.state.engine.get(incident_id).timeline

    @app.get("/api/incidents/{incident_id}/report")
    async def report(incident_id: str, download: bool = False):
        value = app.state.engine.get(incident_id).report
        if value is None:
            raise HTTPException(409, "The report is generated after containment verification.")
        if download:
            return JSONResponse(value.model_dump(mode="json"), headers={"Content-Disposition":f'attachment; filename="{incident_id}-incident-report.json"'})
        return value

    @app.post("/api/incidents/{incident_id}/approval")
    async def approval(incident_id: str, payload: ApprovalRequest):
        return await app.state.engine.approve(incident_id, payload)

    @app.post("/api/incidents/{incident_id}/{command}")
    async def control(incident_id: str, command: str):
        if command not in {"pause", "resume", "skip", "reset"}:
            raise HTTPException(404, "Unknown simulation control.")
        return await app.state.engine.control(incident_id, command)

    @app.websocket("/ws/incidents/{incident_id}")
    async def stream(socket: WebSocket, incident_id: str):
        if socket.headers.get("origin") and socket.headers["origin"] not in ORIGINS:
            await socket.close(code=1008)
            return
        try:
            queue = app.state.engine.subscribe(incident_id)
        except KeyError:
            await socket.close(code=1008)
            return
        await socket.accept()
        reader = asyncio.create_task(socket.receive())
        pending = None
        try:
            while True:
                pending = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait({reader, pending}, return_when=asyncio.FIRST_COMPLETED)
                if reader in done:
                    message = reader.result()
                    if message.get("type") == "websocket.disconnect":
                        break
                    if message.get("text") != "ping":
                        await socket.close(code=1008, reason="Only ping messages are accepted.")
                        break
                    await socket.send_json({"type":"PONG"})
                    reader = asyncio.create_task(socket.receive())
                if pending in done:
                    await socket.send_json(pending.result())
                else:
                    pending.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pending
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            app.state.engine.unsubscribe(incident_id, queue)
            reader.cancel()
            if pending:
                pending.cancel()
            await asyncio.gather(*(task for task in (reader, pending) if task), return_exceptions=True)

    return app


app = create_app()
