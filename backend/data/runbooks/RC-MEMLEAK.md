# RC-MEMLEAK: Memory leak in fraud scoring

Signal: memory_usage ramps linearly, then latency_p99 follows (40-120 min lead).

## Steps
1. Confirm a linear memory slope with no matching traffic increase.
2. Check the deploy log (a deploy may have introduced it).
3. Estimate time to exhaustion at the current slope.
4. Open a ticket to Risk & Compliance with the slope evidence.
5. Schedule the restart in a low-traffic window.

## Preventive action
Restart the service (HITL, simulated); later fix the leak.
