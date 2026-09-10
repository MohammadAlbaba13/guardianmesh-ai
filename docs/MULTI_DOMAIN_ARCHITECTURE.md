# GuardianMesh AI multi-domain architecture

GuardianMesh has one execution engine and seven data-driven Domain Packs. The core owns lifecycle sequencing, typed incident state, graph traversal, policy gates, approval, provider execution, WebSocket snapshots, SQLite persistence and evidence reports. Packs own operational meaning.

## Domain Packs

| Pack | Runnable scenario | Distinct operational result |
|---|---|---|
| `identity` | Suspicious Identity Re-Registration | Restricts the affected session and records step-up verification as still required. |
| `smart_city` | Compromised Camera, SIM/Identity Risk, Energy Control | Protects declared services, applies QoD and isolates bounded Smart City sources. |
| `fintech` | High-Value Payment After SIM Change | Restricts a payment session, requires step-up and preserves banking services. |
| `tourism` | Visitor Trust and Cultural Experience Degradation | Verifies location context, discovers a reachable edge and protects an immersive service while preserving emergency access. |
| `industry` | Industrial Edge Control Abuse | Protects production/safety routes and requires approval for shared edge isolation. |
| `climate` | Flood Alert and Emergency Congestion | Treats weather as an environmental event, prioritizes emergency flows and stabilizes modeled congestion without isolating sensors. |
| `open_innovation` | Regional Multi-Service Trust Cascade | Correlates identity and connectivity signals across a shared regional dependency graph. |

Each pack declares `DomainMetadata`, a unique topology, service roots, priority targets, required-trust context, typed `SignalDefinition` records, a scenario catalog, detection rule, permitted semantic capabilities, response policy, domain metrics and residual verification. The registry in `backend/app/domains/registry.py` is the only selection point. Adding an eighth pack means defining the same `DomainPack` contract, registering it, and adding catalog tests; core lifecycle code does not gain a domain conditional.

## Shared lifecycle

`Sentinel → Impact → Response → Compliance → Network → Report` runs for every pack. Sentinel validates the pack's typed evidence and returns an interpretation; MITRE techniques are included only when the event is a defensible cyber mapping. Impact traverses directed enabled threat paths and calculates a bounded exposure/trust score. Response creates an ordered plan from the pack policy. Compliance validates semantic capability IDs, target scope, route continuity and approvals in a dry-run copy. Network calls the selected provider and the core applies the provider result to the twin. Residual impact, continuity, domain metrics and reports are calculated from the resulting state.

The optional `local_llm` reasoner is advisory only. It receives bounded incident evidence and allowed capability IDs, returns a strict `ReasoningRecommendation`, and can never edit a plan or call a provider. Missing Ollama, malformed output or unsupported references fall back to deterministic reasoning with a visible reason. The default `deterministic` reasoner is offline and authoritative for safety.

## Capability and provider boundary

`backend/app/capabilities/registry.py` describes semantic capabilities such as SIM Swap, Number Verification, Device Swap, Location Verification, Device Reachability, Simple Edge Discovery and Quality on Demand. Protected routing, quarantine, session restriction, shared-segment isolation, step-up and stabilization are explicitly GuardianMesh conceptual controls. Internal endpoint labels are not presented as production REST contracts.

`SimulatedNetworkProvider` is the default and returns a validated envelope containing `provider`, `mode: SIMULATED`, `simulated: true`, `capability`, `summary` and evidence. `GUARDIANMESH_NETWORK_PROVIDER=camara|nokia` currently keeps the simulator active with a truthful missing-authorized-binding notice. No undocumented network request or fake live response is possible. A reviewed future adapter would need exact operator OpenAPI versions, authorized sandbox credentials/consent, device identifiers, asynchronous session handling, idempotency and compensating actions.

## Run and verify

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

The application is designed to run without internet after dependencies are installed. Docker configuration is supplied in `compose.yaml`; the current development host does not have a Docker CLI, so image/build execution must be verified on a Docker-enabled host.

## Trust and safety

All events are synthetic defensive simulations. The policy layer rejects critical-service isolation, validates every target and capability, protects required routes before shared actions, records approval actors, and verifies the resulting graph. Domain-specific trust reduction is not identity proof, payment reversal, physical factory actuation or weather prediction.
