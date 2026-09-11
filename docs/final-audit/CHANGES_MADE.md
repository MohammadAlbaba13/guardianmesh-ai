# Changes Made During Final Audit

| File | Problem | Change | Reason | Verification |
|---|---|---|---|---|
| `backend/app/engine.py` | Demo timer could auto-approve LIVE/AUTO | Automation now applies only to SIMULATION without manual approval; effective value is persisted | Preserve human-in-the-loop safety | Backend tests, runtime checks |
| `backend/app/providers/service.py` | Deleted QoD session retained verified state | Record `NOT_VERIFIED`, `ENDED`, cleanup status, and historical summary | Prevent stale live evidence | QoD tests |
| `frontend/src/App.tsx` | UI could advertise auto-approval for LIVE | Disable toggle outside SIMULATION and force manual approval in request | Align UI with backend safety gate | Frontend test and browser rehearsal |
| `frontend/src/components/Topology.tsx` | Inspector showed initial risk after containment | Display residual risk when available | Keep visualization consistent with final state | Browser hero rehearsal |
| `backend/tests/test_live_network.py` | Missing regression coverage for approval and deletion state | Added targeted tests | Lock down confirmed defects | 26 targeted tests passed |
| `frontend/src/App.test.tsx` | Missing LIVE approval regression | Added visible-control assertion | Protect human gate | 22 frontend tests passed |
| `docs/final-audit/*` | Required final audit evidence absent | Added report, matrix, changes, runtime evidence and inventories | Submission readiness | Clean-start audit |

All other changed files listed by `git status` belong to the preceding GuardianMesh multi-domain implementation and were preserved.
