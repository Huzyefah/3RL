# Pitch: 7-minute script

| Time | Beat | On screen |
|---|---|---|
| 0:00 | Customers wait about 6 minutes on a failing payment; the average outage lasts 84. On PS-02, a static threshold catches **0 of 28** incidents. | Scorecard, raw CSV panel |
| 0:40 | Lower it to 95% and you catch **28 of 28**, but **44%** of pages are false (precision 0.56). A single row can't separate them; context can, and gathering it is the agents' job. | Same panel |
| 1:10 | Meet NovaPay: 8 PS-02 services as a Pakistani wallet with partner banks. We replay your 500 rows; dense data between anchors is generated and labelled synthetic replay. | Architecture |
| 1:40 | Predict and re-plan: replay 08-01. ETA counts down, the Skeptic disputes, the Commander re-plans and routes with a grounded RCA. | Live Ops, incident trace |
| 3:00 | Noise killed: the salary-day surge is argued down, calendar cited; "FP avoided" goes up. | Alert feed |
| 3:30 | Act, live: inject `bank_c_slow`, approve reroute BANK_C, watch success recover and the Commander verify and close. | Demo, approvals, Live Ops |
| 5:30 | Prove: see live scorecard (computed from the CSV, never hard-coded). | Scorecard |
| 6:20 | Scale and business: agents only run on grouped candidates; per-monitored-service SaaS for wallets, PSPs and banks. Ask. | Slide |

Not built yet, so not demoed: Security Sentinel autonomy beat, GCP deployment.

## Q&A cheat sheet

- **"Your data is synthetic."** The 500 PS-02 rows are kept exactly; everything between them comes from a seeded, committed generator and is labelled. The sandbox is a real running system with real faults and fixes.
- **"Doesn't your generator favour your detector?"** Hard negatives ramp like incidents, some false alarms have no benign explanation, some incidents are abrupt, and deploys and salary days coincide with real incidents.
- **"Did you overfit?"** We tune only on a training split; reported numbers come from held-out data.
- **"Is it safe for an AI to reroute payments?"** Only with approval, only to a healthy target, idempotent, audited and reversible. Ledger and limit changes are denied outright.
- **"What if OpenAI is down?"** A deterministic template fallback keeps the pipeline running.
- **"Privacy?"** Tools return aggregates and redacted samples; a test blocks MSISDNs from prompts; secrets belong in Secret Manager.
- **"Cost?"** The detector is O(1) per point and LLM cost scales with grouped candidates, not raw events.
