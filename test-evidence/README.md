# test-evidence

Screenshots and reports that prove each phase gate. Layout:

```
test-evidence/phase-NN-<slug>/
  REPORT.md                  gate record (template in the plan); evidence table is generated
  <flow-slug>/NN-<step>.png  one folder per flow, explicit step indices
  <flow-slug>/recording.gif  hero flows only (claude-in-chrome)
  reports/                   pytest --html and small JSON/XML reports
```

- Write PNGs only through `shot()` in `e2e/support/evidence.ts` (or `scripts/plot_*.py` and `scripts/render_json.py` for backend phases). Never hand-copy screenshots.
- Only the current phase writes evidence (`EVIDENCE_PHASE=phase-NN-<slug>`). Earlier folders are read-only.
- Flows required per phase live in `scripts/phases.json`. `uv run python scripts/evidence_index.py phase-NN-<slug>` fails on a flow without a PNG and rewrites the table between the `<!-- evidence:start -->` and `<!-- evidence:end -->` markers in REPORT.md.
- Committed: PNG, GIF, REPORT.md, small JSON/XML. Gitignored: traces, videos, HTML reports, `test-results/`.
