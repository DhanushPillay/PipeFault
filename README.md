# PipeFault

A reproducible fault-injection benchmark for operator-level data defects in streaming ML pipelines, on three real public datasets, plus a label-free early-warning evaluation.

**Status:** week 1 baseline. The clean TLC ETA reference is implemented and verified on the full 2024 data. Olist is implemented but pending Kaggle credentials.

## The problem

Production ML pipelines rarely fail loudly. A join fans out, a dimension arrives late, a watermark drops events, or a schema change coerces a type. The job succeeds, the dashboard stays green, and the model degrades silently. Existing research injects dataset-level errors into static tables. It does not model pipeline operators, event time, compounding defects, or the delay before labels reveal damage.

## What this project builds

1. An 8-defect taxonomy mapped to real pipeline operators.
2. A deterministic event-time simulator and a config-driven fault injector.
3. A measurement study of single and compounding defects on three real public datasets: NYC TLC, Olist, and UCI Online Retail II.
4. A label-free degradation predictor evaluated against ATC and static thresholds, with lead time and false-alarm rate.
5. A working demo: FastAPI endpoint, Streamlit dashboard, Docker Compose.

## What this project is not

- Not a general data-quality tool or a production monitor.
- Not a new ML algorithm. The contribution is measurement, a harness, and evidence.
- Not a claim that observability replaces labels. It tests when observability helps and when it does not.

## Research gap

Existing work measures dataset-level data-quality defects on static tables, and separate work studies feature freshness. We found no controlled study that measures how operator-level defects in a streaming pipeline compound, or whether observability metadata predicts the damage before labels arrive.

## Planned repository layout

```text
pipefault/
  data/         # download, audit, schemas, splits
  features/     # as-of joins, task features
  inject/       # defect injectors
  simulate/     # deterministic event-time simulator
  observe/      # per-batch signal extraction
  predict/      # degradation predictor and baselines
  api/          # FastAPI service
  dashboard/    # Streamlit app
configs/
  datasets/
  defects/
  experiments/
data/           # downloaded, never committed
docs/
tests/
paper/
```

## Current status

- Environment is locked to Python 3.12 with `uv.lock`.
- `pipefault data download`, `data audit`, and `data manifest` work.
- TLC 2024-01 and the full 2024 year, plus the Online Retail II audit, are verified on real data.
- `pipefault baseline` trains and evaluates the clean TLC ETA reference with MLflow tracking.
- CI runs lint, format, type checks, tests, and a Docker build.
- `docs/litmatrix.md` contains 37 DOI-verified papers plus 5 arXiv-only sources.
- Olist download is implemented but has not run because Kaggle credentials are not configured yet.

## Prerequisites

- Python 3.12 (uv installs it from `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop for the demo image
- A free Kaggle account for Olist: `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` / `KAGGLE_KEY`

## Quickstart

Windows PowerShell:

```powershell
.\make.ps1 install
uv run pipefault data download --dataset tlc --month 01
uv run pipefault data download --dataset retail
uv run pipefault data audit
uv run pipefault baseline
```

Linux/macOS:

```bash
make install
uv run pipefault data download --dataset tlc --month 01
uv run pipefault data download --dataset retail
uv run pipefault data audit
uv run pipefault baseline
```

Download the full TLC year and Olist once credentials are configured:

```bash
uv run pipefault data download
uv run pipefault data manifest --verify
```

Planned next: `make pilot`, `make experiment`, `make reproduce`, and `make demo`.

## Clean TLC baseline

The seed-42 reference uses 500k train, 150k validation, and 150k test rows, selected by stable hash from 39,180,316 clean rows. Splits are by month: January-June train, July-September validation, October-December test, with the last day of each earlier split embargoed. All features are known at pickup time.

| Split | Model | RMSE | MAE | R² |
|---|---|---:|---:|---:|
| validation | global median | 14.605 | 9.144 | -0.112 |
| validation | zone median | 11.765 | 7.704 | 0.279 |
| validation | LightGBM | 6.743 | 4.335 | 0.763 |
| test | global median | 15.043 | 9.458 | -0.134 |
| test | zone median | 12.563 | 8.228 | 0.209 |
| test | LightGBM | 7.201 | 4.613 | 0.740 |

Best iteration was 522 under a 2,000-round cap; training took about 25 seconds on 8 threads. Across seeds 42-44, test RMSE is 7.19 ± 0.01 and validation RMSE is 6.80 ± 0.05 (mean ± sample SD). These are the clean-reference numbers against which defect conditions will be measured.

MLflow stores runs in `mlflow.db` and model artifacts in `mlruns/`. Per-run metrics and the model are also written to `artifacts/baseline/tlc.json` and `artifacts/baseline/tlc_model.txt`.

## Documentation

| File | Purpose |
|---|---|
| `docs/DATASETS.md` | Sources, licenses, schemas, tasks, splits, leakage exclusions, alternatives |
| `docs/PREREGISTRATION.md` | Research questions, hypotheses, falsification criteria, analysis plan |
| `docs/RESEARCH.md` | Literature landscape, gap, contributions, novelty boundaries |
| `docs/litmatrix.md` | 37 DOI-verified papers with claim, method, data, metric, and threat |
| `docs/ARCHITECTURE.md` | Components, data flow, interfaces, drop conditions |
| `docs/EXPERIMENTS.md` | Defect mechanics, grid, baselines, metrics, statistics |
| `docs/ROADMAP.md` | 12-week plan, deliverables, success criteria, kill criteria |
| `docs/PUBLICATION.md` | Venues, paper structure, figures, ethics, submission checklist |

## Timeline

Twelve weeks plus four weeks of buffer. Week 3 contains a go/no-go pilot on TLC. If most defect conditions show less than 2% degradation, stop and re-scope before building the full harness. The other two datasets are wired in week 4.

## Data and licenses

- NYC TLC yellow taxi 2024: NYC Terms of Use. Downloaded by script, not committed. Verified full year: 41,169,720 rows, 526,866 invalid durations.
- Olist Brazilian e-commerce: CC BY-NC-SA 4.0. Non-commercial, share-alike. Requires Kaggle credentials; not committed.
- UCI Online Retail II: CC BY 4.0, DOI 10.24432/C5CG6D. Downloaded by script. Verified: 1,067,371 rows, 22.8% missing CustomerID.

No synthetic data is used. Defects are injected into real records as the experimental treatment; the clean run is the reference. Details and exact splits are in `docs/DATASETS.md`.

## License

Code: MIT. Documentation: CC BY 4.0. Datasets retain their original licenses.

## Citation

Placeholder until the artifact DOI is assigned.
