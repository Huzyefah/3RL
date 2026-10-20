# sim/ → finpay-sim (NovaPay sandbox; sandbox only, never a real system)

One FastAPI process: `/pay` → fraud → ledger pool semaphore (20) → the rail chosen by `routing[bank]` (mock banks BANK_A–E, Raast) · OTP providers P1/P2 · `/login` · a traffic loop (20–80 payments/s) · an emitter.

```
uv sync && uv run pytest
uv run uvicorn finpay_sim.app:app --port 8081
```

## Contract (consumed by sentinel-api executors and the Demo screen)
- `POST /chaos/{bank_c_slow|ledger_pool_leak|otp_p1_down|report_batch|reset}`, plus `cred_stuffing` in P1.
- `GET|POST /admin/routing` (bank → rail), `/admin/otp` (active provider), `/admin/workers`, `/admin/throttle` (P1).
- **Emitter:** every 5 s it publishes one CES message per service carrying all of that service's metrics (FINAL_PLAN §4.3), to the bus locally or the `telemetry` Pub/Sub topic on GCP. `source="finpay-sim"`.
- All state is in memory, so the service is **single-instance** (min=max=1, no CPU throttling).
- It is private on Cloud Run. Only `sa-api` holds `run.invoker`.
- Fault and recovery behaviour must be deterministic under a fixed seed, so the tests can simulate time.
