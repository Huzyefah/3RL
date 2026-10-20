# RC-DBPOOL: DB connection pool leak or slow query

Signal: connection_pool rises convexly, then latency, then errors (10-40 min). Can cascade AuthService to PaymentGateway.

## Steps
1. Check the deploy log for a change in the last 30 min.
2. Inspect pool use vs active sessions; look for long-running queries.
3. Check dependants (blast radius) for cascading errors.
4. If a deploy caused it, propose rollback; otherwise propose scale.
5. Page the owning team; verify pool use falls below 0.75 u.

## Preventive action
Scale the service (HITL, cap 5 instances) or roll back the deploy (HITL, simulated).
