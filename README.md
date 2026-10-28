# PipeFault

A reproducible fault-injection benchmark for operator-level data defects in streaming ML pipelines, on three real public datasets, plus a label-free early-warning evaluation.

**Status:** week 0 scaffold. TLC and Online Retail II download and audit paths are verified on real data; Olist is implemented but pending Kaggle credentials.

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
- CI runs lint, format, type checks, tests, and a Docker build.
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
```

Linux/macOS:

```bash
make install
uv run pipefault data download --dataset tlc --month 01
uv run pipefault data download --dataset retail
uv run pipefault data audit
```

Download the full TLC year and Olist once credentials are configured:

```bash
uv run pipefault data download
uv run pipefault data manifest --verify
```

Later weeks add `make baseline`, `make pilot`, `make experiment`, `make reproduce`, and `make demo`.

## Documentation

| File | Purpose |
|---|---|
| `docs/DATASETS.md` | Sources, licenses, schemas, tasks, splits, leakage exclusions, alternatives |
| `docs/PREREGISTRATION.md` | Research questions, hypotheses, falsification criteria, analysis plan |
| `docs/RESEARCH.md` | Literature landscape, gap, contributions, novelty boundaries |
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
