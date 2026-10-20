# sim (finpay-sim)

Synthetic payments app that Sentinel observes and controls. Package `finpay_sim`; Phase 5 builds it, so treat the contract below as plan, not as existing code.

## Commands

```
uv run pytest sim/tests
uv run uvicorn finpay_sim.app:app --port 8081 --reload
```

## Contract

- `model.py` holds a pure `SimModel.step(dt, rng)` with no I/O. The async loop wraps it and scales time by `SIM_SPEED`. Test the model without the loop.
- Endpoints: `/pay`, `/login`; banks A-E, OTP providers P1 and P2; traffic 20-80 TPS.
- Chaos: `bank_c_slow`, `ledger_pool_leak`, `otp_p1_down`, `report_batch`, `reset` (Phase 5); `cred_stuffing` (Phase 9); `cert_expiry` with flat metrics (Phase 9).
- Admin: `routing`, `otp`, `throttle`, `workers`; every admin call requires `SIM_ADMIN_TOKEN`.
- Emitter sends CES (validated against `sentinel.schemas.CES`) every 5 s of simulated time; `EMIT_MODE=http|pubsub`.
- Acceptance: under `bank_c_slow`, an executor-driven reroute restores success >= 0.97 within 60 s of simulated time.
