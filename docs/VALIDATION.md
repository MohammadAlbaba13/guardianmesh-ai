# GuardianMesh AI — validation record

Verified locally on Windows on **2026-09-07**. This is a safe, deterministic simulation with no production telecom connectivity.

## Automated checks

| Check | Result |
|---|---|
| Backend `python -m pytest -q` | **59 passed**; two upstream Starlette/TestClient deprecation warnings, no failed tests |
| Frontend `npm test` | **11 passed** across four files |
| Frontend `npm run build` | **Passed**: TypeScript plus Vite production build; no bundle-size warning |
| Backend health | HTTP 200; local simulated provider; six agents |
| Frontend entry | HTTP 200 at `http://127.0.0.1:5173/` |
| JSON export | HTTP 200; attachment filename and complete persisted report verified |
| PowerShell scripts | All three parse; start → stop → both ports released → start exercised successfully |
| Compose | YAML structure, two services, build paths, localhost bindings, persistence volume and proxy configuration checked |
| Docker runtime | **Not run**: Docker is unavailable on this machine |

## Browser rehearsal

The application was operated through the browser: scenario selection, run, report views, reset, restart, pause, resume, skip, manual approval and rejection. Live source and service states were inspected directly; report data was read from the technical-report view rather than inferred from animation.

- **Camera — `GM-2F6C0D23486C`:** 48 observed remote-service sessions against a baseline of 2, with a synthetic exploit signature; T1210; initial hospital exposure 80/100; 11 completed network actions; **19.754 seconds to containment**; source isolated; all six agents complete; residual propagation risk 0; minimum services online 6/6.
- **Identity — `GM-FD6B8A802246`:** T1451; location mismatch; SIM change 12 minutes earlier; derived HIGH identity risk and restricted endpoint trust; **19.783 seconds to containment**; source isolated; minimum services online 6/6.
- **Energy — `GM-A930EB9E7A0B`:** 26 service-stop attempts outside maintenance; T1489; 7 completed network actions; **17.709 seconds to containment**; both source and shared edge segment isolated; minimum services online 6/6. Approval is explicitly recorded as `DEMO_AUTOMATION`. Manual operator approval was also exercised in `GM-7A4700FF34A6`.
- **Guided / manual rejection — `GM-AC4E740C15EC`:** pause held the timeline unchanged; resume and skip progressed the engine. Operator rejection produced plan v2 with six actions, omitted segment isolation, left the edge node online, isolated the source, and retained all six services. Technical reports contain both plan versions and the original approval-required policy. Time spent deliberately paused or waiting for an operator is included in wall-clock duration.
- **Interactive twin:** 14 rendered assets; selection and the asset inspector work; hospital protection and simulated latency of 8 ms were observed. Reset/restart refit the twin and clear the asset selection. Graph scrolling no longer traps normal page scrolling.
- **Reports:** executive and technical views render from incident state. JSON export uses a server attachment endpoint, avoiding reliance on a browser-specific blob-download implementation.
- **Responsive layout:** checked at an actual 1440px desktop viewport and 390px narrow viewport. Document width stayed within the viewport; narrow layout stacks panels; the simulation label remains visible. The graph supports pan/zoom and asset inspection on small screens.

## Reliability fixes covered by regression checks

1. Historical resets cannot release the active incident's pause or approval gates.
2. Approval requirements depend on shared infrastructure scope, not just the action verb.
3. Continuity rejects failed transit assets and offline/isolated services.
4. Binary and unsupported WebSocket messages close cleanly without leaking subscriptions.
5. An accepted operator decision wins a race with demo auto-approval.
6. Rejected plan/policy versions remain in the incident evidence.
7. Contained incidents recover unfinished reports after a restart; orderly shutdown finalizes verified reports.
8. History is ordered by creation time before limiting; recovery inspects all unfinished records.
9. Sentinel requires sufficient structured evidence; a scenario label alone cannot force classification.
10. Initial frontend loading waits for saved-incident restoration before enabling Run.
11. Windows stop handles the virtualenv interpreter child process and checks recorded process identity.

## Presentation configuration

Use one backend worker, local ports **8000 / 5173**, the supplied dependency lockfiles, **Fast pitch**, and **Demo auto-approval enabled**. Run camera once, reset, and keep that scenario selected. Initial dependency installation needs internet; all demo runtime behavior is local.

The prototype does not implement real traffic interception, a production operator adapter, external LLM calls, enterprise authentication, or a real-world service-availability guarantee. Docker deployment still needs a Docker-equipped machine for runtime verification.


Final browser console inspection found **no errors or warnings during the final three-scenario rehearsal**. The command center was reset after verification and left with Camera / Fast pitch / Demo auto-approval selected. Both servers remain running through the verified start script.
