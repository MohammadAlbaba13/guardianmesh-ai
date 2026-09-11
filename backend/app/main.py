import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from .engine import SimulationEngine, Conflict
from .models import StartRequest, ApprovalRequest, Incident
from .persistence import Repository
from .scenarios import scenario_catalog
from .topology import build_topology
from .domains.registry import get_domain, list_domains
from .capabilities.registry import list_capabilities, get_capability
from .agents import initial_agents
from .diagnostics import diagnostics
from .providers.service import NetworkActionService
from .providers.qod import NetworkError

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


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

# Extra trusted hostnames (comma-separated) for the reverse-proxied frontend host in a
# hosted deployment (e.g. Render). The nginx reverse proxy already strips/clears the
# browser's Origin header before forwarding, so this only widens the Host allow-list
# used by TrustedHostMiddleware; local development is unaffected when unset.
_EXTRA_TRUSTED_HOSTS = [h.strip() for h in os.environ.get("GUARDIANMESH_TRUSTED_HOSTS", "").split(",") if h.strip()]


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = Repository(database_url)
        repository.recover()
        app.state.engine = SimulationEngine(repository)
        if isinstance(app.state.engine.provider, NetworkActionService) and not app.state.engine.provider.config.configured:
            logging.getLogger("guardianmesh").warning("LIVE provider unavailable: configure authorized QoD bindings and provider credentials. No live success will be fabricated.")
        yield
        await app.state.engine.close()
        repository.engine.dispose()

    app = FastAPI(title="GuardianMesh AI", version="2.0.0", description="Autonomous Multi-Domain Resilience & Trust Platform. Local simulation; optional advisory AI.", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=sorted(ORIGINS), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "backend", *_EXTRA_TRUSTED_HOSTS])

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

    @app.exception_handler(ValueError)
    async def validation_handler(request, exc):
        message = str(exc)
        if message.startswith("Unknown GuardianMesh domain") or message.startswith("Unknown scenario"):
            return JSONResponse({"detail": message}, status_code=404)
        return JSONResponse({"detail": message}, status_code=422)

    @app.get("/api/health")
    async def health():
        return {"status":"ok", "simulation":True, "provider":"local", "agents":6,
                "critical_services":sum(n.critical for n in build_topology().nodes), "domains":len(list_domains()), "version":"2.0.0"}

    @app.get("/api/v1/diagnostics")
    async def readiness():
        return await diagnostics(app.state.engine)

    @app.websocket("/ws/health")
    async def websocket_health(socket: WebSocket):
        if socket.headers.get("origin") and socket.headers["origin"] not in ORIGINS:
            await socket.close(code=1008)
            return
        await socket.accept()
        await socket.send_json({"status": "READY"})
        await socket.close()

    @app.post("/api/incidents/{incident_id}/actions/{action_id}/{operation}")
    async def session_operation(incident_id: str, action_id: str, operation: str):
        if operation not in ("lookup", "delete", "extend"):
            raise HTTPException(404, "Unsupported session operation")
        engine = app.state.engine
        async with engine.lock:
            incident = engine.get(incident_id)
            if incident.status in ("RUNNING", "PAUSED", "AWAITING_APPROVAL"):
                raise Conflict("Wait for the active run before managing a session")
            action = next((a for a in incident.actions if a.id == action_id), None)
            if action is None: raise HTTPException(404, "Unknown action")
            if operation == "extend" and action.result.get("cleanup") == "DELETED":
                raise Conflict("Deleted sessions cannot be extended")
            manager = engine.provider if isinstance(engine.provider, NetworkActionService) else NetworkActionService("LIVE")
            manager.checkpoint = engine.emit
            try:
                result = await manager.manage(action, incident, operation)
            except NetworkError as exc:
                engine.emit(incident, "SESSION_MANAGEMENT_FAILED", exc.code, "Network")
                raise HTTPException(502, exc.code) from None
            if incident.report:
                from .reporting import generate_report
                incident.report = generate_report(incident)
                engine.repository.save(incident)
                engine.publish(incident)
            return result

    def runtime_metadata():
        engine = app.state.engine
        return {"provider": {"name": engine.provider.name, "mode": engine.provider.mode,
                             "simulated": engine.provider.simulated,
                             "requested": getattr(engine.provider, "requested_mode", "simulated"),
                             "notice": getattr(engine.provider, "notice", None)},
                "reasoner": {"mode": engine.reasoner.mode, "requested": engine.reasoner.requested_mode,
                             "notice": getattr(engine.reasoner, "notice", None)}}

    @app.get("/api/v1/domains")
    async def domains():
        return [pack.metadata for pack in list_domains()]

    @app.get("/api/v1/capabilities")
    async def capabilities():
        return list_capabilities()

    @app.get("/api/v1/runtime")
    async def runtime():
        return runtime_metadata()

    @app.get("/api/v1/domains/{domain_id}")
    async def domain_detail(domain_id: str):
        pack = get_domain(domain_id)
        scenario = next(iter(pack.scenarios.values()))
        preview = Incident(id="PREVIEW", domain_id=domain_id, domain=pack.metadata,
                           category=scenario.category, scenario_id=scenario.id, title=scenario.title,
                           source=scenario.source, mode="fast", auto_approve=True, step_duration=1.7,
                           topology=pack.topology(), telemetry=pack.telemetry(scenario.id), agents=initial_agents())
        return {**pack.metadata.model_dump(), "topology": preview.topology, "scenarios": pack.catalog(),
                "capabilities": [get_capability(k) for k in pack.permitted_capabilities],
                "metrics": pack.metrics(preview), **runtime_metadata()}

    @app.get("/api/v1/domains/{domain_id}/scenarios")
    async def domain_scenarios(domain_id: str):
        return get_domain(domain_id).catalog()

    @app.post("/api/v1/domains/{domain_id}/scenarios/{scenario_id}/start", status_code=201)
    async def domain_start(domain_id: str, scenario_id: str, payload: StartRequest):
        return await app.state.engine.start(scenario_id, payload, domain_id=domain_id)

    @app.get("/api/topology")
    async def topology():
        return build_topology()

    @app.get("/api/scenarios")
    async def scenarios():
        return scenario_catalog()

    @app.get("/api/incidents")
    async def incidents(domain_id: str | None = None):
        if domain_id:
            get_domain(domain_id)
        return [{"id":i.id, "domain_id": i.domain_id, "domain_name": (i.domain or get_domain(i.domain_id).metadata).name,
                 "title":i.title, "status":i.status, "started_at":i.started_at, "has_report":bool(i.report)}
                for i in app.state.engine.repository.list() if domain_id is None or i.domain_id == domain_id]

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
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            app.state.engine.unsubscribe(incident_id, queue)
            reader.cancel()
            if pending:
                pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*(task for task in (reader, pending) if task), return_exceptions=True)

    return app


app = create_app()
