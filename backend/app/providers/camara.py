"""CAMARA integration boundary. No operator transport is installed or invoked."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from urllib.parse import urlparse
from ..capabilities.registry import get_capability
from ..models import Action, Incident
from .base import ProviderUnavailable


class SandboxBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["camara", "nokia"]
    base_url: str
    token: SecretStr
    authorized: bool = False
    api_version: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    device_bindings: dict[str, str] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def https_url(cls, value: str) -> str:
        url = urlparse(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Sandbox URL must use HTTPS without embedded credentials, query or fragment")
        return value.rstrip("/")

    @field_validator("capabilities")
    @classmethod
    def supported_capabilities(cls, values: list[str]) -> list[str]:
        for value in values:
            if get_capability(value).conceptual:
                raise ValueError("Conceptual controls have no generic CAMARA binding")
        return values


class CamaraNetworkProvider:
    name = "CAMARA authorized sandbox adapter boundary"
    requested_mode = "camara"
    mode = "SANDBOX"
    simulated = False
    notice = "Operator transport and device binding require validation; no sandbox connection is active."

    def __init__(self, binding: SandboxBinding | None = None) -> None:
        self.binding = binding

    async def execute(self, action: Action, incident: Incident) -> dict:
        if get_capability(action.kind).conceptual:
            raise ProviderUnavailable("Conceptual GuardianMesh controls cannot be sent to CAMARA")
        if self.binding is None or not self.binding.authorized:
            raise ProviderUnavailable("No explicitly authorized sandbox binding")
        if action.kind not in self.binding.capabilities or action.target not in self.binding.device_bindings:
            raise ProviderUnavailable("Capability or device is outside the authorized sandbox binding")
        raise ProviderUnavailable("Reviewed operator transport is not installed; no request was sent")
