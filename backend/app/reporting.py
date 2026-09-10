from datetime import datetime
from .models import Incident, Report
from .topology import asset, online_services


def generate_report(incident: Incident) -> Report:
    end = incident.ended_at or incident.started_at
    duration = round((datetime.fromisoformat(end)-datetime.fromisoformat(incident.started_at)).total_seconds(), 2)
    completed = [a for a in incident.actions if a.status == "COMPLETE"]
    availability = online_services(incident.topology)
    minimum_online = min((s.online for s in incident.samples), default=availability)
    risk = incident.impact.score if incident.impact else 0
    source = asset(incident.topology, incident.source)
    return Report(executive={
        "headline": "Threat contained. Critical services stayed online." if incident.status == "CONTAINED" else "Incident requires operator attention.",
        "what_happened": f"{incident.title}: {source.name} exhibited {incident.classification.threat_type.lower() if incident.classification else 'anomalous behavior'}.",
        "service_risk": f"Initial projected risk was {risk}/100. {len(incident.impact.critical_services) if incident.impact else 0} critical services were exposed through the dependency graph.",
        "response": incident.plan.strategy if incident.plan else "No plan executed.",
        "actions_completed": len(completed), "availability": f"{availability}/6 critical services online",
        "minimum_services_online": minimum_online, "outcome": incident.outcome,
        "residual_risk": incident.residual_impact.score if incident.residual_impact else None,
        "duration_seconds": duration, "simulation": True,
    }, technical={
        "incident_id": incident.id, "scenario_id": incident.scenario_id,
        "started_at": incident.started_at, "ended_at": incident.ended_at,
        "source_asset": source.model_dump(mode="json"),
        "detection_telemetry": incident.telemetry.model_dump(),
        "classification": incident.classification.model_dump(mode="json") if incident.classification else None,
        "initial_impact": incident.impact.model_dump(mode="json") if incident.impact else None,
        "residual_impact": incident.residual_impact.model_dump(mode="json") if incident.residual_impact else None,
        "plan": incident.plan.model_dump(mode="json") if incident.plan else None,
        "plan_history": [p.model_dump(mode="json") for p in incident.plan_history],
        "agent_decisions": [a.model_dump() for a in incident.agents],
        "policy": incident.policy.model_dump() if incident.policy else None,
        "policy_history": [p.model_dump(mode="json") for p in incident.policy_history],
        "approval_history": [a.model_dump() for a in incident.approvals],
        "network_actions": [a.model_dump() for a in incident.actions],
        "timeline": [e.model_dump() for e in incident.timeline],
        "service_samples": [s.model_dump() for s in incident.samples],
        "final_state": incident.status, "outcome": incident.outcome,
        "scope": "Local deterministic simulation; conceptual endpoints; no production Nokia/CAMARA connectivity.",
    })
