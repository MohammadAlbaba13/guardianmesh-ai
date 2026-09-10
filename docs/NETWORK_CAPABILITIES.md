# Network capability boundary

GuardianMesh uses semantic capabilities through `backend/app/capabilities/registry.py`. The default provider is local and deterministic. Every result carries `mode: SIMULATED` and `simulated: true`; the simulator never opens a socket.

| Capability | Meaning in GuardianMesh | Status |
|---|---|---|
| SIM Swap | Records recent SIM change; correlated fraud/trust risk is GuardianMesh interpretation. | SIMULATED; CAMARA semantics documented |
| Number Verification | Checks supplied authenticated mobile-line context; it is not full identity proof. | SIMULATED; CAMARA semantics documented |
| Device Swap | Checks line-to-device association change. | SIMULATED; CAMARA semantics documented |
| Location Verification | Checks expected area using supplied synthetic location-match evidence. | SIMULATED; CAMARA semantics documented |
| Device Reachability | Checks modeled SMS/data reachability. | SIMULATED; CAMARA semantics documented |
| Simple Edge Discovery | Finds a reachable edge by graph path; it does not deploy an application. | SIMULATED; CAMARA semantics documented |
| Quality on Demand | Applies a bounded local priority profile and modeled latency. | SIMULATED; CAMARA/Nokia semantics documented |
| Protected routing | Enables an authored protected route in the twin. | GuardianMesh conceptual simulation |
| Endpoint quarantine | Isolates a non-critical source in the twin. | GuardianMesh conceptual simulation |
| Shared-segment isolation | Isolates a declared shared segment only after route protection and approval. | GuardianMesh conceptual simulation |
| Bounded session protection | Restricts one suspicious session while shared services remain available. | GuardianMesh conceptual simulation |
| Step-up verification | Records that additional verification is required; never claims it succeeded. | GuardianMesh conceptual simulation |
| Operational stabilization | Reduces modeled congestion while retaining source operation and emergency access. | GuardianMesh conceptual simulation |

Official primary references used for capability meaning: [CAMARA SIM Swap](https://camaraproject.org/sim-swap/), [Number Verification](https://camaraproject.org/number-verification/), [Device Swap](https://camaraproject.org/device-swap/), [Location Verification](https://camaraproject.org/location-verification/), [Device Reachability Status](https://camaraproject.org/device-reachability-status/), [Simple Edge Discovery](https://camaraproject.org/simple-edge-discovery/), [Quality on Demand](https://camaraproject.org/quality-on-demand/), and [Nokia QoD sessions](https://networkascode.nokia.io/_docs/quality-on-demand/qod-sessions).

`GUARDIANMESH_NETWORK_PROVIDER=camara` or `nokia` is an integration request, not proof of access. Without a reviewed authorized binding, the active provider remains SIMULATED and exposes a visible notice. The repository contains adapter boundaries that reject execution until credentials, consent, device/application bindings, exact API version and transport are supplied. No fake live response is possible.
