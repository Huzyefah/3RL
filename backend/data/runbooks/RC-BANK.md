# RC-BANK: Partner bank switch degrading

Signal: one bank's latency steps up, then issuer timeouts rise (20-45 min lead).

## Steps
1. Confirm the degradation is isolated to one bank segment (payment_success_rate, issuer_timeout_rate).
2. Check the maintenance calendar; if scheduled, suppress.
3. Check the Raast rail is healthy (u < 0.75 over 5 min).
4. Ask the bank's NOC for status; open a ticket to Payments, CC Digital Channels.
5. After approval, reroute IBFT for that bank via Raast; verify at +60 s.

## Preventive action
Reroute the bank's IBFT via Raast (HITL, idempotent, one-click revert).
