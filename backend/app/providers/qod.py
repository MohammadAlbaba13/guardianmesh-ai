"""Bounded async CAMARA QoD v1 transport; Nokia's documented RapidAPI binding.

Only configured server-side device mappings may leave the machine. POST is never
retried: a timeout can mean the provider created a session without returning its ID.
"""
import asyncio
import ipaddress
import os
from typing import Literal
from urllib.parse import urlparse, quote
from uuid import uuid4
import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, AliasChoices, field_validator, model_validator


class NetworkError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(code)  # Never echo provider bodies, URLs or credentials.


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phoneNumber: str = Field(pattern=r"^\+[0-9]{7,15}$")


class ApplicationServer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ipv4Address: str

    @field_validator("ipv4Address")
    @classmethod
    def valid_ip(cls, v):
        return str(ipaddress.IPv4Address(v))


class QoDRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device: Device
    applicationServer: ApplicationServer
    qosProfile: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    duration: int = Field(default=300, ge=1, le=86400)


class QoDSession(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Retain only whitelisted metadata.
    sessionId: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    qosStatus: Literal["REQUESTED", "AVAILABLE", "UNAVAILABLE"] = Field(validation_alias=AliasChoices("qosStatus", "status"))


class QoDConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["nokia", "camara"] = "nokia"
    sessions_url: str = "https://network-as-code.p-eu.rapidapi.com/quality-on-demand/v1/sessions"
    api_key: SecretStr = SecretStr("")
    bearer_token: SecretStr = SecretStr("")
    rapidapi_host: str = "network-as-code.nokia.rapidapi.com"
    environment: Literal["SANDBOX", "OPERATOR"] = "SANDBOX"
    authorized: bool = False
    bindings: dict[str, QoDRequest] = Field(default_factory=dict)
    timeout: float = Field(default=6, ge=.1, le=15)
    poll_attempts: int = Field(default=3, ge=1, le=5)

    @field_validator("sessions_url")
    @classmethod
    def safe_url(cls, v):
        p = urlparse(v)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment or p.port not in (None, 443):
            raise ValueError("QoD requires an HTTPS URL without credentials or query")
        if p.hostname == "localhost" or "." not in p.hostname or p.hostname.endswith((".local", ".internal")):
            raise ValueError("QoD provider must be a public host")
        try:
            if not ipaddress.ip_address(p.hostname).is_global:
                raise ValueError("Private provider address forbidden")
        except ValueError as exc:
            if "forbidden" in str(exc):
                raise
        if not p.path.endswith("/sessions") or ".." in p.path:
            raise ValueError("Configure the exact supported QoD sessions URL")
        return v.rstrip("/")

    @model_validator(mode="after")
    def reviewed_binding(self):
        if self.provider == "nokia" and self.sessions_url != "https://network-as-code.p-eu.rapidapi.com/quality-on-demand/v1/sessions":
            raise ValueError("Nokia uses the documented QoD v1 RapidAPI binding")
        if self.provider == "camara" and "/v1/" not in self.sessions_url:
            raise ValueError("This adapter supports the CAMARA QoD v1 contract only")
        if self.environment == "SANDBOX" and self.provider == "nokia" and any(not b.device.phoneNumber.startswith("+9999") for b in self.bindings.values()):
            raise ValueError("Nokia SANDBOX requires +9999 test-device phone numbers")
        return self

    @property
    def configured(self):
        credential = self.api_key if self.provider == "nokia" else self.bearer_token
        return self.authorized and bool(credential.get_secret_value()) and bool(self.bindings)

    @classmethod
    def from_env(cls):
        import json
        return cls(provider=os.getenv("GUARDIANMESH_NETWORK_PROVIDER", "nokia") if os.getenv("GUARDIANMESH_NETWORK_PROVIDER") in ("nokia", "camara") else "nokia",
            sessions_url=os.getenv("GUARDIANMESH_QOD_SESSIONS_URL", cls.model_fields["sessions_url"].default),
            api_key=os.getenv("NOKIA_API_KEY", ""), bearer_token=os.getenv("CAMARA_ACCESS_TOKEN", ""),
            authorized=os.getenv("GUARDIANMESH_LIVE_AUTHORIZED", "false").lower() == "true",
            environment=os.getenv("GUARDIANMESH_PROVIDER_ENVIRONMENT", "SANDBOX"),
            bindings=json.loads(os.getenv("GUARDIANMESH_QOD_BINDINGS", "{}")))


class QoDClient:
    def __init__(self, config: QoDConfig, transport=None):
        self.config, self.transport = config, transport

    async def request(self, method, suffix="", payload=None):
        try:
            async with asyncio.timeout(self.config.timeout * 2 + 1):
                return await self._request(method, suffix, payload)
        except TimeoutError:
            raise NetworkError("TIMEOUT_OUTCOME_UNKNOWN" if method == "POST" else "TIMEOUT") from None

    async def _request(self, method, suffix="", payload=None):
        if not self.config.configured:
            raise NetworkError("LIVE_PROVIDER_UNCONFIGURED")
        if self.transport is None:
            import socket
            try:
                addresses = await asyncio.get_running_loop().getaddrinfo(urlparse(self.config.sessions_url).hostname, 443, type=socket.SOCK_STREAM)
            except OSError: raise NetworkError("NETWORK_UNAVAILABLE") from None
            if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise NetworkError("PRIVATE_PROVIDER_ADDRESS_BLOCKED")
        headers = {"Content-Type": "application/json", "X-Correlator": str(uuid4())}
        if self.config.provider == "nokia":
            headers.update({"X-RapidAPI-Key": self.config.api_key.get_secret_value(), "X-RapidAPI-Host": self.config.rapidapi_host})
        else:
            headers["Authorization"] = "Bearer " + self.config.bearer_token.get_secret_value()
        for attempt in range(2 if method == "GET" else 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.config.timeout, connect=min(3, self.config.timeout)),
                        follow_redirects=False, trust_env=False, transport=self.transport) as client:
                    async with client.stream(method, self.config.sessions_url + suffix, json=payload, headers=headers) as response:
                        status = response.status_code
                        if method == "DELETE" and status == 404:
                            return {}, status
                        if status in (429, 502, 503, 504) and method == "GET" and attempt == 0:
                            await asyncio.sleep(.2)
                            continue
                        if status in (401, 403): raise NetworkError("AUTH_FAILED", status)
                        if status == 429: raise NetworkError("RATE_LIMITED", status)
                        if not 200 <= status < 300: raise NetworkError("PROVIDER_ERROR", status)
                        if method == "DELETE":
                            if status != 204: raise NetworkError("DELETE_NOT_CONFIRMED", status)
                            return {}, status
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 65536: raise NetworkError("MALFORMED_RESPONSE", status)
                        import json
                        try: value = json.loads(chunks)
                        except (ValueError, UnicodeError): raise NetworkError("MALFORMED_RESPONSE", status) from None
                        if not isinstance(value, dict): raise NetworkError("MALFORMED_RESPONSE", status)
                        return value, status
            except httpx.TimeoutException:
                if method == "GET" and attempt == 0: continue
                raise NetworkError("TIMEOUT_OUTCOME_UNKNOWN" if method == "POST" else "TIMEOUT") from None
            except httpx.HTTPError:
                raise NetworkError("NETWORK_UNAVAILABLE") from None

    async def session_request(self, method, suffix="", payload=None):
        value, status = await self.request(method, suffix, payload)
        try: return QoDSession.model_validate(value), status
        except ValueError: raise NetworkError("MALFORMED_RESPONSE", status) from None

    async def create(self, binding: QoDRequest):
        return await self.session_request("POST", payload=binding.model_dump())

    async def get(self, session_id):
        return await self.session_request("GET", "/" + quote(session_id, safe=""))

    async def delete(self, session_id):
        return await self.request("DELETE", "/" + quote(session_id, safe=""))

    async def extend(self, session_id, duration):
        if not 1 <= duration <= 86400: raise NetworkError("INVALID_DURATION")
        return await self.session_request("POST", "/" + quote(session_id, safe="") + "/extend", {"requestedAdditionalDuration": duration})
