# RC-ABRUPT: Failure with no precursor

Signal: metrics jump to CRITICAL with no lead signal within 1-2 min.

## Steps
1. Acknowledge that no lead was possible; do not claim prediction.
2. Identify the root-cause service from the dependency graph and blast radius.
3. Create a ticket routed to the root-cause team, symptom team CC'd.
4. Page on-call (P1/P2) and attach the RCA draft.
5. Review the incident for new precursor signals afterwards.

## Preventive action
Reactive only; report as 'no lead possible'.
