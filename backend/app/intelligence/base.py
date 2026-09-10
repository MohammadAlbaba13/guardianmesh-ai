"""Advisory reasoner contract. No reasoner receives an execution capability."""
from typing import Protocol
from ..models import Incident, ReasoningRecommendation


class Reasoner(Protocol):
    mode: str
    requested_mode: str

    async def reason(self, incident: Incident, allowed_capabilities: tuple[str, ...]) -> ReasoningRecommendation: ...


def evidence_catalog(incident: Incident) -> dict[str, str]:
    evidence = {f"evidence:{i}": item for i, item in enumerate(incident.classification.evidence if incident.classification else [])}
    if incident.impact:
        evidence["impact"] = incident.impact.explanation
    return evidence
