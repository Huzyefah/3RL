# Repository context and prior plan review

Inspected `/Users/huzyefah/Other/Atomcamp Hackathon Final/3RL` read-only before authoring. Present working-tree files were a minimal `# 3RL` README, Python/environment ignore rules, the organizer CSV and DOCX. No application code, deployment configuration, dependency file or applicable repository AGENTS.md was present. The working tree also had a pre-existing tracked deletion of `docs/sentinel_hackathon_plan_1.md`. That deletion was preserved. The prior plan was read from Git HEAD as historical design context, not restored or treated as implemented work.

| Prior Sentinel idea | Treatment in this blueprint | Reason |
|---|---|---|
| Pre-incident rather than post-impact story | Retain | Directly aligns with PS-02 |
| Forecast time-to-threshold and mine precursors from original CSV | Replace with separate temporal simulation | Original service/metric streams are too sparse and no onset is supplied |
| Investigator, historian, skeptic, responder and narrator agents | One bounded investigator plus deterministic components | Tool selection and contradiction checks can be demonstrated without five model agents |
| Evidence-cited hypothesis and historical match | Retain with verification status and no-match | Useful rubric alignment; similarity score is not a calibrated probability |
| Live scorecard with lead time from source flags | Split original point metrics from synthetic onset metrics | Point labels cannot establish real warning lead time |
| Change sensitivity immediately on false-positive feedback | Versioned reviewed threshold updates | Avoid unvalidated live adaptation and loss of reproducibility |
| BigQuery as ticket sink | Firestore operational tickets/state, BigQuery optional analytics | Durable mutable operational state and idempotency fit the proposed state machine |
| Google Chat alert and real scaling | Internal durable alert/ticket; simulated retry cap | Simpler reviewable MVP without external messaging or financial authority |
| Eight-hour/two-person schedule | Treat as a past assumption, not confirmed context | User says actual time/team may be unknown; estimate remaining person-hours explicitly |
| Backup recording and clear replay labeling | Retain | Supports reliable, honest presentation |

The historical plan names an event/date/venue and a seven-minute pitch, but those facts were not independently verified against the organizer brief. Do not use them as confirmed current scheduling constraints. A new working tree file must not silently restore the deleted plan. This package adds a new implementation blueprint and preserves source evidence; no commit, push or deployment was performed.
