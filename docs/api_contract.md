# API contract

Proposed API version `/v1`. HTTPS JSON; authenticated user JWT for UI routes and producer/IAM identity for ingestion. Single-tenant `demo` MVP; server derives tenant from identity. All mutations accept `Idempotency-Key` and return a stable operation ID for identical retries. Same key with different payload → 409. Timestamps RFC3339 with explicit timezone, except organizer source timestamps preserved as unzoned source text plus explicitly configured replay event time.

| Method and path | Request | Response / authorization |
|---|---|---|
| POST /events:batch | `{events: TelemetryEvent[]}` <=100 events, total <=256 KiB | 202 `{batch_id,accepted_ids,rejected:[{event_id,code}]}` after publish confirmation; producer only |
| POST /internal/pubsub/telemetry | Pub/Sub wrapped push envelope | 204 only after durable dedup/window/outbox commit; IAM push invoker only |
| POST /internal/pubsub/jobs | Job ID, tenant, episode ID and expected state version | 204 after bounded durable transition; worker-only identity |
| POST /internal/sweep | `{before,limit}` with server-enforced limit <=100 | Reconcile expired leases, publish unsent outbox jobs; Scheduler OIDC only |
| GET /healthz | None | Liveness, no secret or project detail; 200 running |
| GET /readyz | None | 200 if required store/publish dependencies ready, 503 otherwise; LLM can be degraded |
| GET /overview | Optional source_mode, time bounds | `{as_of,freshness,health,early_warnings,queue_risk,mode}`; viewer |
| GET /incidents | Status/service/time/cursor; limit <=50 | `{items,next_cursor}`; viewer |
| GET /incidents/{id} | ID | Typed assessment with source/evidence/action versions; viewer |
| GET /incidents/{id}/timeline | Cursor | `{entries:[{at,kind,actor,evidence_ids,status}],next_cursor}`; viewer |
| GET /incidents/{id}/evidence | start/end/service, <=60 min | Redacted metric/log/span evidence and units; viewer |
| POST /incidents/{id}/actions:propose | `{catalog_action,parameters,evidence_ids,expected_version}` | 202 proposal plus server policy decision; operator |
| POST /actions/{id}:approve | `{expected_version,parameter_hash,expires_at}` | 200 approval bound to actor, tenant, action and version; approver role |
| POST /actions/{id}:reject | `{reason,expected_version}` | 200 rejected receipt; approver |
| GET /actions | status/cursor | `{items,next_cursor}`; viewer |
| POST /incidents/{id}/feedback | `{classification,corrected_cause,comment,expected_version}` | 201 immutable feedback record; operator; no immediate model training |
| GET /replay/scenarios | None | Synthetic catalog, original-data mode, manifest version and explanation; viewer |
| POST /replays | `{fixture_id,mode,speed,intervention_policy}` allowlisted fixture, speed <=60 | 202 `{replay_id,status,synthetic,clock}`; operator; default safe simulation |
| POST /replays/{id}:pause | `{expected_version}` | 200 persisted pause state; operator |
| GET /replays/{id} | ID | `{clock,status,event_counts,baseline,action_world,source_mode}`; viewer |
| GET /evaluation | dataset/version/partition/detector | Counts, denominators, lead distribution, measured/unmeasured status; viewer |

Use short polling with cursor/version every 1–2 s for MVP. SSE is optional; no need for WebSocket infrastructure. Return ETag or state version, and do not cache privileged responses publicly. Mutations require CSRF protections appropriate to the selected session mechanism. Cross-origin UI is deferred unless Vercel is chosen.

Error envelope: `{error:{code,message,retryable,request_id,details}}`. 400 schema/units, 401 unauthenticated, 403 scope/role, 404 unknown resource, 409 version/idempotency mismatch, 413 size, 422 invalid action preconditions, 429 rate limit with Retry-After, 503 transient dependency. Redact underlying credential/provider responses. A replay that cannot ingest an event enters `failed` or `paused_error`; it never skips silently to successful verification.

Action parameters are catalog-specific. MVP `create_internal_ticket` takes incident ID and validated summary reference; `record_alert` takes severity and episode ID; `recommend_runbook` takes a versioned runbook ID; `simulate_retry_cap` takes a simulation namespace, cap 0.02 and duration <=60 windows. No arbitrary SQL, URL, shell command or payment identifiers are accepted.

Telemetry validation includes finite numbers, known service IDs, metric/unit compatibility, source timestamp and namespace. Model output schema is only the evidence-backed assessment subset; policy/approval/execution fields are application-owned. Reject cited evidence IDs not retrieved for the incident or numerical claims inconsistent with evidence. Store original provider output separately with limited retention for debugging; UI displays validated fields only.
