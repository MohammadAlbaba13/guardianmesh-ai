# GuardianMesh judge runbook

## Before the demo

PowerShell, from `C:\Users\LOQ\Documents\ChatGPT\Win`:

```powershell
.\scripts\start.ps1
```

Open http://127.0.0.1:5173/ . API documentation: http://127.0.0.1:8000/docs . Fresh installation: run `scripts\setup.ps1` first. Stop with `scripts\stop.ps1`. Use one backend worker. Do not delete the SQLite database or change ports during judging.

## 30-second check

1. Click **Judge Mode**, then **Check readiness**.
2. Backend and Database must be READY. WebSocket must be CONNECTED (a real handshake).
3. Deterministic AI works offline. For local LLM, verify the configured model is READY; unavailable generation visibly falls back.
4. Nokia without credentials must say UNAVAILABLE. With credentials it can say CONFIGURED / NOT_CHECKED until an actual request or owned-session lookup supplies reachability evidence.
5. Select SIMULATION for the reliable offline rehearsal. For external execution, follow `HACKATHON_LIVE_INTEGRATION.md`, restart the backend, choose LIVE, and check your authorized sandbox binding.

## Hospital hero, with a human decision

1. Keep **Fast pitch**; uncheck **Demo auto-approval**.
2. Select network mode and AI advisor. Leave severity at **Scenario default** (risk 80/100 for camera).
3. Click **Inject Hospital Incident**. It selects Smart City and camera, resetting the previous current incident safely.
4. Follow camera → detection → T1210 → hospital dependency exposure → advisory reasoning → deterministic policy.
5. Open **Why this response**. The execution plan remains deterministic even when AI is selected.
6. At **Operator decision required**, click **Approve** once. Reject stops the proposed execution and produces an audit record.
7. Watch **Critical-flow protection**. In simulation it says SIMULATED / MODELED. A configured successful external run shows LIVE API ACTION, SANDBOX, external session ID, HTTP status, AVAILABLE and VERIFIED. This proves provider QoD establishment, not physical latency improvement.
8. Verify source ISOLATED, residual graph risk 0, six agents complete and 6/6 services online in the modeled twin.
9. Open **City resilience incident report**. Inspect Executive and Technical views; export JSON.
10. **Replay Incident** inspects stored timeline evidence without repeating any external request.
11. **Reset Demo** ends known owned external sessions and resets the twin. If cleanup fails, retry after resolving provider availability; do not erase the record.

Use **Guided** for slower presentation. Pause/Resume/Skip operate on the backend; Skip never bypasses approval. Restart safely resets and launches the selected scenario. Choose Identity or Energy in the scenario selector to show the other two Smart City scenarios; every run uses its own evidence, mapping and plan. Exit Judge Mode to switch among all seven domain packs.

## If Nokia fails

LIVE failures remain failed and never claim successful containment. Keep the session ID if one was returned. Use Verify status or End session on the provider proof card after the run stops. Unknown POST outcomes need inspection in the provider console; no blind create retry occurs.

For a reliable fallback presentation: Reset Demo, choose SIMULATION and rerun. Alternatively choose AUTO and explicitly enable **Allow explicit simulation fallback** before starting. Safe fallback is visibly labeled FALLBACK_SIMULATED. It is suppressed for uncertain create outcomes or existing sessions.

## If Ollama fails

Local LLM mode already falls back deterministically with a visible reason. For consistent pitch timing choose Deterministic. On machines with Ollama installed, provision a small model before judging with `ollama pull qwen2.5:0.5b`; configure its name in `.env`. No models are downloaded by a scenario run. Model weights live in Ollama's storage, not the repository.

## Troubleshooting

| Symptom | Check |
|---|---|
| Browser cannot load | Run start script; inspect `.logs/frontend.err.log` and port 5173 |
| Backend offline | `.logs/backend.err.log`; health endpoint; dependencies; port 8000 |
| WebSocket unavailable | Same-origin Vite `/ws` proxy; backend running; one worker; permitted localhost Origin |
| QoD AUTH_FAILED | Correct application key and subscription; no trailing whitespace; restart after `.env` change |
| QoD malformed/unavailable | Correct provider v1 binding and authorized test device/profile; retain the failed evidence |
| Reset blocked | In-flight request must finish; known sessions must be deleted successfully before reset |
| Twin does not update | Confirm live event stream; reconnect/reload restores full backend snapshot |
| Local model fallback | `ollama list`, configured model name, loopback endpoint and timeout |

No external API key is needed for the offline demo. A real Nokia sandbox request requires a user-owned application key from the Nokia console; never put it in chat, screenshots or committed source.
