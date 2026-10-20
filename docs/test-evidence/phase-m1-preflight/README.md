# Phase −1: Preflight

**Command:** `infra/preflight.sh` (read-only, re-runnable). Raw output: [preflight/preflight.txt](preflight/preflight.txt)

| Check | Result |
|---|---|
| Toolchain (gcloud, uv, node, npm, python3.12) | PASS |
| gcloud account `huzyefahsaqib13@gmail.com`, project `mda-atomcamp`, roles/owner | PASS |
| Billing enabled (`billingAccounts/01A094-D71AD3-175CE4`) | PASS (linked by user 2026-10-20) |
| PS-02 CSV = 500 rows | PASS |
| `OPENAI_API_KEY` valid | **PENDING**: user to add it to `.env`; needed from Phase 4 (live) on |
| `CHAT_WEBHOOK_URL` | WARN: absent → UI "Chat card" panel fallback |

**Plugins installed (user scope):** playwright, frontend-design, context7, pyright-lsp, typescript-lsp.

**Deviation:** the gate is passed with the OpenAI key deferred. Phases 0–3 don't call OpenAI; the key is re-checked at the Phase 4 gate.

## Gate checklist
- [x] Billing enabled
- [x] Owner role + project set
- [x] Data present
- [ ] OpenAI key (deferred to Phase 4, by design)
