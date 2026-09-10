"""Validated provider results and the guarded execution boundary."""
from typing import Literal, Protocol, Any
from pydantic import BaseModel, ConfigDict, model_validator
from ..models import Action, Incident


EvidenceValue = str | bool | int | float | None | list[str]


class CapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    mode: Literal["SIMULATED", "SANDBOX", "LIVE"]
    simulated: bool
    capability: str
    summary: str
    evidence: dict[str, EvidenceValue]

    @model_validator(mode="after")
    def mode_is_truthful(self):
        if self.simulated != (self.mode == "SIMULATED"):
            raise ValueError("Provider mode and simulation flag disagree")
        return self


class NetworkProvider(Protocol):
    name: str
    mode: str
    requested_mode: str
    notice: str | None
    simulated: bool

    async def execute(self, action: Action, incident: Incident) -> dict[str, Any]: ...


class ProviderUnavailable(RuntimeError):
    """Provider cannot execute within its authorized binding."""
