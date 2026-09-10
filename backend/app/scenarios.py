from dataclasses import dataclass
from .models import Technique, Telemetry


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    subtitle: str
    source: str
    severity: float
    threat_type: str
    confidence: float
    evidence: tuple[str, ...]
    technique_id: str
    technique_name: str
    tactic: str
    explanation: str
    domain: str = "Enterprise"
    requires_approval: bool = False

    def technique(self) -> Technique:
        return Technique(id=self.technique_id, name=self.technique_name, tactic=self.tactic, domain=self.domain,
                         explanation=self.explanation, url=f"https://attack.mitre.org/techniques/{self.technique_id.replace('.', '/')}/")


SCENARIOS = {
    "camera": Scenario("camera", "Compromised IoT Camera", "Lateral movement · hospital exposure", "camera", .96,
        "IoT lateral movement", .97,
        ("Camera opened 48 unauthorized remote-service sessions in 10 seconds; baseline is 2.",
         "Simulated exploit signature observed against the telecom gateway remote service.",
         "Destination route leads to hospital and emergency service dependencies."),
        "T1210", "Exploitation of Remote Services", "Lateral Movement",
        "An exploit signature and unauthorized remote-service attempts indicate attempted lateral movement, not scanning alone."),
    "identity": Scenario("identity", "Telecom Identity / SIM-Swap Risk", "Identity anomaly · trusted endpoint", "sensor", .88,
        "Suspected telecom identity takeover", .91,
        ("Trusted sensor identity re-registered from an unexpected city zone.",
         "SIM replacement occurred 12 minutes before the authentication anomaly.",
         "Owner-confirmation flag is absent in the synthetic identity record."),
        "T1451", "SIM Card Swap", "Initial Access",
        "A recent SIM change plus an unconfirmed identity transfer and location anomaly supports a suspected SIM-swap mapping. A SIM change alone is not proof of compromise.", "Mobile"),
    "energy": Scenario("energy", "Energy & City Control Threat", "Control-plane abuse · shared segment", "traffic", .99,
        "Unauthorized infrastructure control", .98,
        ("Traffic controller sent 26 unauthorized service-stop requests to the edge compute plane.",
         "Command source is outside the signed controller maintenance window.",
         "Shared edge segment supplies energy telemetry and smart-city control."),
        "T1489", "Service Stop", "Impact",
        "Unauthorized service-stop commands attempt to disrupt the edge services supporting energy and city control. This is an Enterprise mapping for the compute layer, not a full ICS assessment.",
        requires_approval=True),
}


def scenario_catalog() -> list[dict]:
    return [{"id": s.id, "title": s.title, "subtitle": s.subtitle, "source": s.source,
             "requires_approval": s.requires_approval} for s in SCENARIOS.values()]


def scenario_telemetry(scenario_id: str) -> Telemetry:
    return {
        "camera": Telemetry(remote_sessions=48, baseline_sessions=2, exploit_signature=True),
        "identity": Telemetry(sim_swap_minutes_ago=12, ownership_confirmed=False, location_matches=False),
        "energy": Telemetry(service_stop_requests=26, maintenance_window=False),
    }[scenario_id]
