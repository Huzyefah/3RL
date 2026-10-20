# RC-AUTH-ATTACK: Credential stuffing

Signal: login failures burst across many accounts from few sources (5-20 min lead).

## Steps
1. Check auth-failure z-score and login_failure_rate on AuthService.
2. Count distinct accounts per source over 5 min; compare with the guard thresholds.
3. Exclude allowlisted sources (corporate, partner banks, processors).
4. Throttle qualifying sources (TTL 15 min); step up MFA on targeted accounts if OTP is healthy.
5. Verify at +60 s: failures down by 50% and legitimate success within 1% of baseline; else roll back and page.

## Preventive action
Throttle attacking sources (AUTO, guarded, shadow mode first).
