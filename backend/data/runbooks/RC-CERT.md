# RC-CERT: Expired certificate or config error

Signal: metrics are flat; only a novel log template appears.

## Steps
1. Review the novel log template and its first occurrence time.
2. Check certificate expiry and recent config changes for that service.
3. Identify the affected downstream callers.
4. Open a ticket and page the owning team.
5. Renew the certificate or revert the config.

## Preventive action
Ticket and page; add certificate-expiry monitoring.
