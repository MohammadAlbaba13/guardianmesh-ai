"""Semantic network intent routing with per-action provenance and durable checkpoints."""
import asyncio
from .simulated import SimulatedNetworkProvider
from .qod import QoDClient, QoDConfig, NetworkError
from ..models import now


class NetworkActionService:
    # The twin always uses simulated controls. Only explicitly bound QoD is external.
    simulated = False
    mode = "SIMULATED"  # Configuration is never proof of an executed network call.
    def __init__(self, execution_mode="SIMULATION", allow_fallback=False, config=None, transport=None):
        self.execution_mode, self.allow_fallback = execution_mode, allow_fallback
        self.config_error = None
        try: self.config = config or QoDConfig.from_env()
        except (ValueError, TypeError):
            self.config = QoDConfig()
            self.config_error = "Invalid live configuration; review server environment variables."
        self.client = QoDClient(self.config, transport)
        self.local = SimulatedNetworkProvider()
        self.requested_mode = self.config.provider
        self.name = f"{self.config.provider.upper()} QoD + local digital twin controls"
        self.notice = "Only bound QoD actions contact the provider. All topology, containment and metrics remain modeled."
        self.checkpoint = None
        self._lock = asyncio.Lock()
        self._attempted = set()
        self.last_reachability = "NOT_CHECKED"

    def diagnostic(self):
        return {"configured": self.config.configured, "provider": self.config.provider,
                "environment": self.config.environment, "api": "Quality on Demand v1",
                "execution_mode": self.execution_mode, "reachability": self.last_reachability,
                "bound_targets": sorted(self.config.bindings), "fallback_enabled": self.allow_fallback,
                "notice": self.config_error or (self.notice if self.config.configured else "LIVE PROVIDER UNAVAILABLE: configure authorized QoD bindings and provider credentials.")}

    def record(self, action, incident, event, **values):
        action.result.update(values)
        action.result.setdefault("lifecycle", []).append({"event": event, "timestamp": now(), **values})
        if self.checkpoint: self.checkpoint(incident, event, f"{action.target}: {event.replace('_', ' ')}", "Network")

    async def execute(self, action, incident):
        # Non-QoD and unbound targets are explicitly declared local-only scopes.
        if self.execution_mode == "SIMULATION" or action.kind != "qod" or (self.config.configured and action.target not in self.config.bindings):
            result = await self.local.execute(action, incident)
            result.update(execution_state="SIMULATED", verification="MODELED", timestamp=now(),
                          scope="Local digital twin; no external request")
            return result
        async with self._lock:
            key = (incident.id, action.id)
            if key in self._attempted:
                if action.result.get("verification") == "VERIFIED": return action.result
                raise NetworkError("DUPLICATE_EXECUTION_BLOCKED")
            self._attempted.add(key)
            self.record(action, incident, "NETWORK_REQUEST_STARTED", provider=self.config.provider,
                mode="LIVE_FAILED", simulated=False, execution_state="SENDING", capability="qod",
                provider_environment=self.config.environment, operation="POST QoD sessions v1",
                verification="PENDING", timestamp=now(), fallback=False)
            try:
                if not self.config.configured: raise NetworkError("LIVE_PROVIDER_UNCONFIGURED")
                binding = self.config.bindings.get(action.target)
                if not binding: raise NetworkError("TARGET_NOT_BOUND")
                session, status = await self.client.create(binding)
                self.last_reachability = "REACHABLE"
                self.record(action, incident, "QOD_SESSION_CREATED", mode="LIVE", execution_state="ACCEPTED",
                            external_session_id=session.sessionId, http_status=status, qos_status=session.qosStatus,
                            profile=binding.qosProfile, duration=binding.duration)
                for attempt in range(self.config.poll_attempts):
                    current, status = await self.client.get(session.sessionId)
                    if current.sessionId != session.sessionId: raise NetworkError("SESSION_ID_MISMATCH", status)
                    self.record(action, incident, "QOD_SESSION_LOOKUP", qos_status=current.qosStatus, lookup_http_status=status)
                    if current.qosStatus == "AVAILABLE": break
                    if current.qosStatus == "UNAVAILABLE": raise NetworkError("QOD_UNAVAILABLE", status)
                    if attempt + 1 < self.config.poll_attempts: await asyncio.sleep(.3 * (2 ** attempt))
                else: raise NetworkError("VERIFICATION_PENDING")
                self.record(action, incident, "NETWORK_VERIFIED", execution_state="LIVE", verification="VERIFIED",
                    summary="QoD session established and verified through provider GET. No latency improvement measured.")
                return action.result
            except NetworkError as exc:
                self.last_reachability = "UNAVAILABLE" if exc.code in ("NETWORK_UNAVAILABLE", "TIMEOUT", "LIVE_PROVIDER_UNCONFIGURED") else "REQUEST_FAILED"
                self.record(action, incident, "LIVE_FAILED", execution_state="LIVE_FAILED", error=exc.code,
                            http_status=exc.status, verification="NOT_VERIFIED", summary="Live QoD failed: " + exc.code)
                # Never hide a potentially active external session behind a local fallback.
                if self.execution_mode == "AUTO" and self.allow_fallback and not action.result.get("external_session_id") and exc.code not in ("TIMEOUT_OUTCOME_UNKNOWN", "MALFORMED_RESPONSE", "NETWORK_UNAVAILABLE"):
                    local = await self.local.execute(action, incident)
                    local.update(lifecycle=action.result["lifecycle"], execution_state="FALLBACK_SIMULATED",
                                 fallback=True, live_error=exc.code, verification="MODELED", timestamp=now())
                    action.result = local
                    self.record(action, incident, "FALLBACK_ACTIVATED", summary="Explicit AUTO fallback: " + local["summary"])
                    return action.result
                raise

    async def manage(self, action, incident, operation, duration=300):
        session_id = action.result.get("external_session_id")
        if not session_id: raise NetworkError("NO_EXTERNAL_SESSION")
        if action.result.get("provider") != self.config.provider: raise NetworkError("PROVIDER_MISMATCH")
        async with self._lock:
            if operation == "delete":
                _, status = await self.client.delete(session_id)
                self.record(action, incident, "QOD_SESSION_DELETED", qos_status="UNAVAILABLE", cleanup="DELETED", cleanup_http_status=status,
                            verification="NOT_VERIFIED", execution_state="ENDED",
                            summary="External QoD session ended; historical creation evidence retained.")
            else:
                session, status = await (self.client.extend(session_id, duration) if operation == "extend" else self.client.get(session_id))
                if session.sessionId != session_id: raise NetworkError("SESSION_ID_MISMATCH", status)
                self.record(action, incident, "QOD_SESSION_" + operation.upper(), qos_status=session.qosStatus,
                            verification="VERIFIED" if session.qosStatus == "AVAILABLE" else "NOT_VERIFIED", lookup_http_status=status)
        return action.result

    async def cleanup(self, incident):
        for action in incident.actions:
            if action.result.get("external_session_id") and action.result.get("cleanup") != "DELETED":
                try: await self.manage(action, incident, "delete")
                except NetworkError as exc:
                    self.record(action, incident, "QOD_CLEANUP_FAILED", cleanup="FAILED", cleanup_error=exc.code)
                    raise
