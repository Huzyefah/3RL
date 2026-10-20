# infra

GCP scripts for Phase 8b and 12; nothing here runs before then. Region `asia-south1`.

- Planned files: `bootstrap.sh` (idempotent), `deploy.sh`, `iam.sh`, `scheduler.sh`, `bq_schema.sql`.
- Every script honours `DRY_RUN=1` (print commands, run none) and passes shellcheck. Check with `DRY_RUN=1 bash infra/deploy.sh`.
- Least-privilege service accounts; secrets in Secret Manager, never in files. `CloudRunScaler` is scoped to `finpay-sim` only.
- Cloud Run: sentinel-api min 1 / max 1, CPU always allocated, `--timeout=3600`; sentinel-web mints an ID token for the private API (D2). Containers must run with a read-only root fs and honour `PORT`.
- gcloud and bq are not installed locally; the user completes plan task 0.11.
- Run security-review on the deployed surface before closing Phase 12.
