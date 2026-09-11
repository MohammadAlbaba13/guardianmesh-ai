from datetime import datetime
from .models import Incident, Report
from .topology import asset, online_services
from .domains.registry import get_domain


def generate_report(incident: Incident) -> Report:
    end = incident.ended_at or incident.started_at
    duration = round((datetime.fromisoformat(end)-datetime.fromisoformat(incident.started_at)).total_seconds(), 2)
    completed = [a for a in incident.actions if a.status == "COMPLETE"]
    availability = online_services(incident.topology)
    minimum_online = min((s.online for s in incident.samples), default=availability)
    risk = incident.impact.score if incident.impact else 0
    source = asset(incident.topology, incident.source)
    domain = incident.domain or get_domain(incident.domain_id).metadata
    total = sum(n.critical for n in incident.topology.nodes)
    return Report(domain_id=incident.domain_id, domain=domain, executive={
        "domain_id": incident.domain_id, "domain_name": domain.name, "theme": domain.theme,
        "execution_mode": incident.execution_mode, "metrics_source": "SIMULATED DIGITAL TWIN",
        "provider_mode": incident.provider_mode, "reasoner_mode": incident.reasoner_mode,
        "category": incident.category, "total_services": total,
        "headline": domain.outcome_label if incident.status == "CONTAINED" else "Incident requires operator attention.",
        "what_happened": f"{incident.title}: {source.name} exhibited {incident.classification.threat_type.lower() if incident.classification else 'anomalous behavior'}.",
        "service_risk": f"Initial projected risk was {risk}/100. {len(incident.impact.critical_services) if incident.impact else 0} critical services were exposed through the dependency graph.",
        "response": incident.plan.strategy if incident.plan else "No plan executed.",
        "actions_completed": len(completed), "availability": f"{availability}/{total} {domain.services_label.lower()}",
        "minimum_services_online": minimum_online, "outcome": incident.outcome,
        "residual_risk": incident.residual_impact.score if incident.residual_impact else None,
        "duration_seconds": duration, "simulation": incident.provider_mode == "SIMULATED",
        "metrics_before": [m.model_dump() for m in incident.metrics_before],
        "metrics_after": [m.model_dump() for m in incident.metrics],
    }, technical={
        "incident_id": incident.id, "scenario_id": incident.scenario_id,
        "schema_version": incident.schema_version, "domain_id": incident.domain_id,
        "domain": domain.model_dump(), "category": incident.category,
        "provider": {"name": incident.provider_name, "mode": incident.provider_mode, "notice": incident.provider_notice},
        "reasoner_mode": incident.reasoner_mode,
        "reasoning": incident.reasoning.model_dump() if incident.reasoning else None,
        "metrics_before": [m.model_dump() for m in incident.metrics_before],
        "metrics_after": [m.model_dump() for m in incident.metrics],
        "total_services": total,
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
        "scope": "All incidents, topology and metrics are modeled. Only actions with mode LIVE have external QoD evidence; provider_environment distinguishes sandbox from operator. QoD status does not measure latency.",
        "limitations": ["Results measure the declared digital twin, not physical outcomes.",
                        "Containment and trust controls remain simulated. External QoD is limited to explicitly bound targets.",
                        "Optional AI advice cannot authorize or execute actions."],
    })
