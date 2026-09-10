"""Repeatable interpretations of validated domain evidence and computed graph risk."""
from ..models import Incident, ReasoningRecommendation
from .base import evidence_catalog


class DeterministicReasoner:
    mode = "deterministic"

    def __init__(self, requested_mode: str = "deterministic", fallback_reason: str | None = None):
        self.requested_mode = requested_mode
        self.fallback_reason = fallback_reason

    async def reason(self, incident: Incident, allowed_capabilities: tuple[str, ...]) -> ReasoningRecommendation:
        priorities = sorted((n for n in incident.topology.nodes if n.critical), key=lambda n: (n.priority, -n.criticality, n.id))
        return ReasoningRecommendation(requested_mode=self.requested_mode,
            interpretation=incident.classification.reasoning if incident.classification else "Awaiting validated domain classification.",
            risk_rationale=incident.impact.explanation if incident.impact else "Graph impact has not been calculated.",
            priorities=[n.id for n in priorities],
            action_rationale=["Protect declared critical dependencies before source remediation.",
                "Only domain-permitted capabilities may enter deterministic planning and Compliance.",
                "Require matching operator approval for shared-impact operations."],
            evidence_refs=list(evidence_catalog(incident)), fallback_reason=self.fallback_reason)
