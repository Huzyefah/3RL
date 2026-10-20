# RC-QUEUE: Settlement consumers under-provisioned

Signal: queue_depth lag accelerates ahead of the 16:00 PKT cut-off (60-180 min lead).

## Steps
1. Compare current lag growth with the usual EOD plateau (cron schedule).
2. Estimate time to cut-off at the current drain rate.
3. Check consumer count and any stuck partitions.
4. Notify Core Banking Ops; propose scaling consumers.
5. Verify lag growth turns negative within 10 min.

## Preventive action
Scale settlement consumers (HITL, capped at 5 instances).
