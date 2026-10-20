# RC-BENIGN: Not an incident

Signal: known benign pattern: salary day, campaign, maintenance, EOD batch, deploy blip, or transient spike.

## Steps
1. Match the pattern against the business calendar, cron schedule and deploy log.
2. Confirm the trend is recovering or the surge is in proportion to TPS.
3. Check no independent failure signal (errors, timeouts) is hiding in the surge.
4. Record the benign evidence and suppress, or schedule a silent recheck.

## Preventive action
Suppress or watch (schedule_recheck, at most 2 per incident).
