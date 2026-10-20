# RC-OTP-PROVIDER: SMS provider degrading

Signal: otp_delivery_rate falls and OTP latency rises for one provider (10-30 min lead).

## Steps
1. Compare P1 and P2 delivery rate; confirm only one provider is affected.
2. Confirm the healthy provider has u < 0.75 over the last 5 min.
3. Notify Digital Channels and the provider's support contact.
4. After approval, fail over to the healthy provider; verify delivery recovers.
5. Note OTP failure blocks payments; treat as tier 0.

## Preventive action
Fail over the OTP route to the healthy provider (HITL, revertible).
