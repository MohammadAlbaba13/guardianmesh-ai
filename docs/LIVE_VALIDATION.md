# GuardianMesh AI live validation record

This record describes the locally validated prototype state. It separates the
deterministic digital twin from the optional external Network-as-Code boundary;
the browser and test evidence below do not claim that a real carrier network
was changed.

## Validation snapshot

| Area | Result | Evidence |
|---|---|---|
| Backend API, SQLite snapshots, reports | PASS | Full `backend/tests` run; persisted incident and report assertions |
| WebSocket lifecycle | PASS | Test handshake, event stream, reconnect/reset and browser readiness check |
| Frontend tests | PASS | 21 Vitest tests |
| Frontend production build | PASS | `npm run build`, 2,296 modules transformed |
| Seven domain packs | PASS | REST catalog and browser selector; 9 deterministic scenarios |
| Smart City digital twin | PASS | 14 nodes, graph dependencies, 6 critical services |
| Six-agent workflow | PASS | Sentinel, Impact, Response, Compliance, Network, Report |
| MITRE mapping and graph impact | PASS | Deterministic T1210 camera mapping and bounded graph risk |
| Human approval and controls | PASS | Manual approval, reject, pause, resume, skip, restart and reset tests/browser rehearsal |
| Local AI | PASS | Ollama `qwen2.5:0.5b`, CPU-only setting, captured in `live-ai-evidence.json` |
| QoD provider boundary | PASS locally | Typed Nokia/CAMARA v1 client, lifecycle tests, truthful unavailable state without credentials |
| Real Nokia sandbox call | NOT VERIFIED | Requires an operator-owned RapidAPI/Nokia application key and authorized binding |
| Docker runtime | NOT VERIFIED | Docker CLI is not installed on this host |

## Browser rehearsal

The final clean judge rehearsal used the actual localhost command center. It
confirmed Judge Mode readiness, a real WebSocket connection, Guided timing,
pause/resume/skip, local LLM reasoning, manual approval, source camera
isolation, residual risk 0, six agents complete, and 6/6 modeled critical
services online. The Smart City React Flow graph rendered all 14 nodes after
containment; node wrappers are given stable dimensions so state updates do not
leave the twin hidden while React Flow re-measures.

The displayed latency and service availability remain simulated digital-twin
metrics. A successful external QoD card is evidence of provider API session
establishment and verification only; it is not proof of measured physical
latency improvement.

## External QoD boundary

Nokia Network-as-Code Quality-on-Demand v1 is implemented with the documented
RapidAPI host, API-key authentication, test-device validation, create/status/
extend/delete lifecycle, bounded polling, response-size limits, safe retries,
owned-session cleanup, and explicit LIVE/SIMULATION/AUTO provenance. Generic
CAMARA v1 is supported through a configured HTTPS endpoint and pre-authorized
bearer token. No secret is stored in this repository, and no real provider
request was attempted during this validation because no operator credential
was available.

To verify the external boundary, an operator must place a valid key and an
authorized sandbox binding in a local ignored `.env`, restart the backend,
choose LIVE, and run the camera hero with manual approval. The run must show
`LIVE_API_ACTION`, a provider session ID, HTTP status, `AVAILABLE` and
`VERIFIED`; otherwise the UI remains honest about the failed or unavailable
state. Never paste the key into chat or commit it.

## Known limits

- Generic CAMARA authorization/token acquisition and webhook callbacks are
  operator-specific; the implementation uses bounded polling.
- Physical carrier controls beyond QoD, measured network telemetry, enterprise
  identity, and production egress/DNS pinning are outside this local prototype.
- An uncertain external POST is never retried automatically. Reset preserves
  evidence and blocks until an owned session is confirmed deleted.
- Docker deployment was not exercised on this Windows host.
