# PS 02 strategy and evidence package

Recommend **PayGuard**, a payment retry-cascade investigation and prevention demo. Start with the [implementation blueprint](docs/implementation_plan.md), then review the [computed EDA](reports/eda/eda_report.md) and [executed evaluation](reports/evaluation/evaluation_report.md). This package contains completed analysis, research, planning, data utilities and synthetic experiments. It is not an implemented or deployed product.

## Read in decision order

1. [Requirements and acceptance](docs/requirements_traceability.md) and [source excerpt](docs/source_brief_excerpt.txt).
2. [Product options](docs/product_strategy.md), [data strategy](docs/data_strategy.md) and [data quality](reports/eda/data_quality_report.md).
3. [Architecture](docs/architecture.md), [detection/agent workflow](docs/detection_and_agent_workflow.md), [API](docs/api_contract.md) and `contracts/`.
4. [Frontend](docs/frontend_experience.md), [security](docs/security_and_risk.md), [cost/deployment](docs/cost_and_deployment.md), [evaluation protocol](docs/evaluation_plan.md) and [demo](docs/demo_and_judging_strategy.md).
5. [Research sources](docs/research_sources.md), [repository context](docs/repository_context.md), [provenance](docs/provenance.json) and [artifact checks](reports/verification.json).

## What the evidence supports

Original: 500 records, 28 incident flags, no source onset/cause; ratio-based point diagnostic, no valid original lead-time claim. Synthetic final test: 18 incident runs, 30 nonincident runs; proposed statistical rule warned on 18/18 with median nine simulated minutes and two negative-run false alarms. These results depend on one designed simulator and are not real payment-system validation. Model quality, agent behavior and cloud performance remain unmeasured.

## Reproduce

Use Python 3.12 and a clean virtual environment. From this package root:

```bash
python -m pip install -r requirements-analysis.txt
python src/eda.py
python src/scenarios.py
python src/validate_artifacts.py
```

Open `notebooks/ps02_eda.ipynb` with this root as the working directory; the first cell resolves root from either root or notebooks/. Scripts use only local files, no model API or cloud credentials. Raw CSV is unchanged; processed/synthetic outputs are separate. Predictions/data are deterministic for the pinned environment; compute timings may vary. Do not treat replay speed as streaming throughput. Package source files may be copied into the existing repository's docs/reports/notebooks/src/contracts/diagrams/data directories while preserving its original README and source DOCX.

`data/scenarios/manifest.json` contains all hidden fault/ground-truth fields. Feature CSVs exclude targets/fault labels; run keys and timestamps are metadata, excluded by an explicit detector allowlist. Never expose manifests to the investigator during a benchmark. `reports/evaluation/exploratory_pilot` documents a prior failed detector/simulator iteration; its inspected test is not the final test.
