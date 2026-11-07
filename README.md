# PipeFault

A reproducible fault-injection benchmark for operator-level data defects in streaming ML pipelines, on three real public datasets, plus a corruption-space law of damage and detectability.

**Status:** week 1 baseline. The clean TLC ETA reference is implemented and verified on the full 2024 data. The MovieLens 32M download and natural-defect audit are implemented and verified on the full dataset. The research design now includes a corruption-space law; the harness does not compute its components yet.

## The problem

Production ML pipelines rarely fail loudly. A join fans out, a dimension arrives late, a watermark drops events, or a schema change coerces a type. The job succeeds, the dashboard stays green, and the model degrades silently. Existing research injects dataset-level errors into static tables. It does not model pipeline operators, event time, compounding defects, or the delay before labels reveal damage.

## What this project builds

1. An 8-defect taxonomy mapped to real pipeline operators.
2. A deterministic event-time simulator and a config-driven fault injector.
3. A measurement study of single and compounding defects on three real public datasets: NYC TLC, MovieLens 32M, and UCI Online Retail II.
4. A corruption-space law: every condition is annotated with decision, distribution, and coverage displacement, and a low-dimensional model predicts damage and whether monitors see the defect before labels arrive.
5. A label-free degradation predictor evaluated against ATC and static thresholds, with lead time and false-alarm rate.
6. A working demo: FastAPI endpoint, Streamlit dashboard, Docker Compose.

## What this project is not

- Not a general data-quality tool or a production monitor.
- Not a new ML algorithm. The core contribution is an empirical law plus a measurement study, a harness, and evidence.
- Not a claim that observability replaces labels. It tests when observability helps and when it does not.

## Research gap

Existing work measures dataset-level data-quality defects on static tables, studies feature freshness, and builds debuggers that explain failures after they happen. We found no controlled study that measures how operator-level defects in a streaming pipeline compound, predicts their damage from a low-dimensional corruption vector, or predicts whether observability metadata sees the defect before labels arrive.

## Planned repository layout

```text
pipefault/
  data/         # download, audit, schemas, splits
  features/     # as-of joins, task features
  inject/       # defect injectors
  simulate/     # deterministic event-time simulator
  observe/      # per-batch signal extraction
  analyze/      # corruption annotation, damage law, detectability
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
- TLC 2024-01 and the full 2024 year, plus the MovieLens 32M and Online Retail II audits, are verified on real data.
- `pipefault baseline` trains and evaluates the clean TLC ETA reference with MLflow tracking.
- CI runs lint, format, type checks, tests, and a Docker build.
- `docs/litmatrix.md` contains 43 DOI-verified papers plus 5 arXiv-only sources.
- The research and experiment plans specify the corruption-space law and silence index (`docs/RESEARCH.md`, `docs/PREREGISTRATION.md`, `docs/EXPERIMENTS.md`); these are design only, with no code yet.
- MovieLens 32M downloads without credentials: 32,000,204 ratings, 2,000,072 tags, 87,585 movies, 200,948 users; all four GroupLens MD5 checks pass. The natural-defect audit found 7,080 movies without genres, 3,153 movies without ratings, and zero duplicate ratings.

## Prerequisites

- Python 3.12 (uv installs it from `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop for the demo image

## Quickstart

Windows PowerShell:

```powershell
.\make.ps1 install
uv run pipefault data download --dataset tlc --month 01
uv run pipefault data download --dataset movielens
uv run pipefault data audit
uv run pipefault baseline
```

Linux/macOS:

```bash
make install
uv run pipefault data download --dataset tlc --month 01
uv run pipefault data download --dataset movielens
uv run pipefault data audit
uv run pipefault baseline
```

Download the full TLC year and MovieLens together:

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
| `docs/litmatrix.md` | 43 DOI-verified papers with claim, method, data, metric, and threat |
| `docs/ARCHITECTURE.md` | Components, data flow, interfaces, drop conditions |
| `docs/EXPERIMENTS.md` | Defect mechanics, corruption-space annotation, grid, baselines, metrics, statistics, law protocol |
| `docs/ROADMAP.md` | 12-week plan, deliverables, success criteria, kill criteria, tiers, top-tier extension |
| `docs/REPRODUCIBILITY.md` | Config hashing, seeds, data pins, determinism tests, replay |
| `docs/SIMULATOR_VALIDATION.md` | Spark row-level agreement gate and downgrade rule |
| `docs/PUBLICATION.md` | Venues, paper structure, figures, ethics, submission checklist |

## Timeline

Twelve weeks plus four weeks of buffer. Week 3 contains a go/no-go pilot on TLC. If most defect conditions show less than 2% degradation, stop and re-scope before building the full harness. The other two datasets are wired in week 4. The top-tier extension in months 4-9 is conditional on the law passing its gates in week 7; if it fails, the measurement study goes to a workshop or journal venue instead.

## Data and licenses

- NYC TLC yellow taxi 2024: NYC Terms of Use. Downloaded by script, not committed. Verified full year: 41,169,720 rows, 526,866 invalid durations.
- MovieLens 32M: GroupLens research license. Research use only, no commercial use; redistribution only under the same terms. Downloaded by script, not committed. Verified: 32,000,204 ratings, 2,000,072 tags, 87,585 movies, 200,948 users; cite Harper & Konstan 2015, DOI 10.1145/2827872.
- UCI Online Retail II: CC BY 4.0, DOI 10.24432/C5CG6D. Downloaded by script. Verified: 1,067,371 rows, 22.8% missing CustomerID.

No synthetic data is used. Defects are injected into real records as the experimental treatment; the clean run is the reference. Details and exact splits are in `docs/DATASETS.md`.

## License

Code: MIT. Documentation: CC BY 4.0. Datasets retain their original licenses.

## Citation

Placeholder until the artifact DOI is assigned.

## Scientific-first scope

The primary deliverable is evidence, not a large technology stack. The first
gate is a controlled TLC pilot with four defects, clean paired controls, at
least three seeds, and frozen monitoring baselines. The first publishable
result extends that pilot to all eight defects and adds a fitted corruption-space
law with one transfer test. Later datasets, compounding, and infrastructure are
extensions only after this grid is interpretable.

The study must report both positive and null results. A defect counts as useful
only when its mechanism is explicit, its affected units are measured exactly,
and its effect can be compared with the clean run. Monitoring is evaluated by
lead time, detection delay, false alarms, precision, recall, and cost, not by a
single model-quality number.

The baseline workload is designed for one local machine. Polars, DuckDB, and
CPU LightGBM are sufficient for the first study. Process TLC by monthly
partition, keep one or two workers on a 16 GB machine, and defer GPU models,
Spark, Redpanda, the API, and the dashboard unless they answer a specific
research question or support reproducibility.
