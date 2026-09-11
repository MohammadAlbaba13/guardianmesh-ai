"""Read-only readiness checks. Never create a session just to report readiness."""
import os
import httpx
from sqlalchemy import text
from .providers.service import NetworkActionService
from .providers.qod import NetworkError
from .intelligence.llm import LocalLLMReasoner


async def diagnostics(engine):
    try:
        with engine.repository.engine.connect() as connection: connection.execute(text("SELECT 1"))
        database = "READY"
    except Exception: database = "UNAVAILABLE"
    live = engine.provider if isinstance(engine.provider, NetworkActionService) else NetworkActionService("LIVE")
    network = live.diagnostic()
    network["execution_mode"] = engine.current.execution_mode if engine.current else os.getenv("GUARDIANMESH_NETWORK_MODE", "SIMULATION")
    # A saved owned session is the only safe authenticated reachability probe.
    saved = next((a for i in engine.repository.list() for a in i.actions
                  if a.result.get("external_session_id") and a.result.get("provider") == live.config.provider
                  and a.result.get("cleanup") != "DELETED"), None)
    if network["configured"] and saved:
        try:
            await live.client.get(saved.result["external_session_id"])
            network["reachability"] = "REACHABLE"
        except NetworkError as exc: network["reachability"] = exc.code
    model = os.getenv("GUARDIANMESH_OLLAMA_MODEL", "")
    ai = {"state": "UNAVAILABLE", "model": model, "deterministic": "READY"}
    try:
        configured = LocalLLMReasoner(os.getenv("GUARDIANMESH_OLLAMA_BASE_URL", "http://127.0.0.1:11434"), model)
        async with httpx.AsyncClient(timeout=2, trust_env=False, follow_redirects=False) as client:
            response = await client.get(configured.base_url + "/api/tags")
            response.raise_for_status()
            names = [m.get("name") for m in response.json().get("models", [])]
            ai["state"] = "READY" if model in names or model + ":latest" in names else "MODEL_MISSING"
    except (ValueError, httpx.HTTPError, TypeError, KeyError): pass
    return {"backend": "READY", "database": database, "ai": ai, "network": network,
            "websocket": "PROBE_REQUIRED", "hero_domain": "smart_city", "hero_scenario": "camera"}
