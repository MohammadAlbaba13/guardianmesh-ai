# Final Test Matrix

| ID | Area | Test | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|---|
| API-01 | Startup | Backend health after clean start | Ready, six agents, six services | `ok`, 6, 6 | PASS | 2026-09-11 |
| API-02 | Startup | Frontend HTTP load | HTTP 200 and GuardianMesh shell | HTTP 200 | PASS | Vite 5173 |
| API-03 | API | OpenAPI, domains, capabilities, runtime, diagnostics | Valid responses | Passed runtime script | PASS | |
| API-04 | Validation | Invalid payloads, unknown IDs, bad origin/host | 4xx without traceback | Passed | PASS | |
| WS-01 | WebSocket | Incident snapshot stream and ping | Ordered snapshots, PONG | Passed | PASS | |
| WS-02 | WebSocket | Malformed message/origin/unknown incident | Close 1008 and cleanup | Passed backend tests | PASS | |
| ENG-01 | Engine | Camera, identity, energy | Contained, risk 0, report | Passed | PASS | Three Smart City scenarios |
| ENG-02 | Engine | Seven domain API/WebSocket runs | All contained and reset | 9/9 passed | PASS | `docs/live-rehearsal.json` |
| ENG-03 | Controls | Pause, resume, skip, restart, reset | Correct gates and clean state | Passed | PASS | |
| ENG-04 | Approval | Stale plan, approve, reject | Versioned human gate | Passed | PASS | |
| ENG-05 | Agents | Six agent lifecycle | All complete | Passed | PASS | |
| AI-01 | MITRE | Deterministic mappings | Correct scenario mapping | T1210/T1451/T1489 | PASS | Non-cyber packs omit MITRE |
| AI-02 | Risk | Directed graph analysis | Coherent initial/residual risk | 80→0 hero | PASS | |
| NET-01 | Simulator | Per-action provenance | SIMULATED/MODELED | Passed | PASS | |
| NET-02 | QoD | Mocked lifecycle and failures | Redacted, fail-closed | 26 tests passed | PASS | Live transport not externally verified |
| UI-01 | Browser | Seven domain cards and topology | Load and switch | Passed | PASS | |
| UI-02 | Browser | Camera hero | 14 nodes, isolation, 6/6 | Passed | PASS | |
| UI-03 | Browser | Guided identity and energy approval | Correct controls/outcomes | Passed | PASS | |
| UI-04 | Browser | Reports and replay | Executive, technical, replay | Passed | PASS | |
| TEST-01 | Backend | `pytest backend/tests -q` | Green | 141 passed, 2 warnings | PASS | |
| TEST-02 | Frontend | `npm test` | Green | 22 passed | PASS | |
| TEST-03 | Frontend | `npm run build` | Green production bundle | PASS | PASS | 2296 modules |
| TEST-04 | Python | `compileall`, `pip check` | No errors | Passed | PASS | |
| SEC-01 | Security | Secret/config scan | No tracked secrets | No matches; `.env` untracked | PASS | |
| SEC-02 | Dependencies | `npm audit` | No high/critical | 2 moderate Vitest findings | PARTIAL | Major upgrade deferred |
| OPS-01 | Docker | Compose build/run | Verified container path | Not available on host | NOT VERIFIED | External dependency |
| OPS-02 | Nokia/CAMARA | Real sandbox call | Provider evidence | Not available | NOT VERIFIED | Credentials/binding required |
