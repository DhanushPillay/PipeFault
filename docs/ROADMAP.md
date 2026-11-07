# Roadmap

Twelve weeks plus four weeks of buffer. Each week has one primary deliverable and a testable success criterion. Do not start the next week until the current criterion passes or a deviation is recorded. The tier (minimum / primary / full) is chosen before the sweep and recorded in `docs/PREREGISTRATION.md`; never run the full grid first.

## 1. Weekly plan

| Week | Tasks | Deliverable | Success criteria | Tag |
|---|---|---|---|---|
| 0 | Repo scaffold, literature matrix, environment, three datasets, natural-defect audit | `docs/litmatrix.md`, `make data`, `make audit` | At least 40 verified papers with DOIs (43 present); three downloads reproducibly hashed; natural defect rates recorded | `v0.0-scaffold` |
| 1 | TLC ETA baseline, time split, leakage checklist | Baseline notebook and `pipefault baseline` | RMSE stable across seeds; leakage checks pass; no post-pickup features | `v0.1-baseline` |
| 2 | Injector v1: D1-D4 with tests, configs, hashing | `pipefault/inject/`, `configs/` | Deterministic; exact affected counts; 20 tests pass; config hash recorded | `v0.2-injector` |
| 3 | Full 8-defect taxonomy + metadata track, TLC 40-condition pilot, annotation module (alpha, gamma), MLflow, **go/no-go** | Experiment runner, pilot report, annotation v1 | Pilot complete; median degradation at least 2%; at least one silent defect evades PSI/KS; alpha and gamma recorded for every run. If go, extend to 8 defects x 5 severities x 2 models x 3 seeds = 240 TLC runs | `v0.3-pilot` |
| 4 | MovieLens and Online Retail II pipelines, cross-dataset check | Three domains, leakage report | Joins correct; label windows covered by embargoes; no opposite-signed surprise left unexplained | `v0.4-datasets` |
| 5 | Compounding: 28 pairs, 5 triples, RERI decomposition; law fit v1 on alpha and gamma | Interaction table, heatmap, law report | CIs computed; at least 3 pairs with CI excluding zero, or documented null; corruption-only model beats the lookup table by 10% on held-out defects, or the failure is recorded | `v0.5-interactions` |
| 6 | Observability module, 30 signals, drift and confidence panel; beta annotation | `pipefault/observe/`, beta in run records | Signals computed per batch; invariant tests; no future data; frozen thresholds recorded | `v0.6-signals` |
| 7 | Early-warning predictor, ATC/AC/DoC/MCD baselines; H6 detectability test | Model, evaluation, detectability report | MAE, R2, lead time, false-alarm table; silence index correlates with recall and lead time (Spearman at least 0.3, AUC at least 0.7), or the failure is recorded | `v0.7-predictor` |
| 8 | Spark validation on 3 conditions (real-data subsets) | Validation report | At least 99% row-level agreement, or streaming claim downgraded and documented | `v0.8-validation` |
| 9 | FastAPI, Streamlit, Docker Compose (only if pilot interpretable) | Demo | `docker compose up` works; dashboard shows defect, predicted degradation, lead time | `v1.0-demo` |
| 10 | Final grid (chosen tier), ablations, figures; law refit and transfer | Results bundle, R6 and R7 | All conditions complete; every figure generated from configs; law refit with the full vector and transferred to MovieLens and Retail | `v1.1-results` |
| 11 | Paper draft v1 | `paper/main.tex` | Every claim backed by a result; all references verified | `paper-v1` |
| 12 | Internal review, artifact, Zenodo DOI, arXiv, submission prep | Submission package | Reproducibility check on a clean machine passes | `v1.2-submission` |
| 13-16 | Buffer, journal extension, rebuttals | Extended draft | Additional dataset or analysis | optional |

## 2. Go/no-go at week 3

Run 4 defects (D1 volume, D5 volume, D3 silent, D6 silent) x 5 severities x 2 models = 40 conditions.

- **Go:** median relative degradation is at least 2% for most conditions, and at least one silent defect is invisible to PSI/KS at the frozen threshold.
- **Re-scope:** if degradation is flat, reframe as a negative-result measurement paper, drop to the minimum grid, or switch to SchemaMiner.
- **Do not:** continue building the full harness on hope.

## 3. Kill criteria

| Trigger | Action |
|---|---|
| Week 3 pilot is flat | Re-scope, drop to minimum grid, or switch project |
| Week 4 cross-dataset check shows opposite-signed effects | Report as domain dependence; do not pool without an interaction term |
| Week 5 law fails to beat the lookup table | Drop the law from the headline; keep the measurement study and report the negative result |
| Week 6 signals require future data | Redesign signals; do not proceed |
| Week 7 silence index does not rank recall or lead time | Report detectability as defect-specific; do not claim the index generalizes |
| Week 8 simulator agreement below 99% | Drop the streaming claim; report as micro-batch simulator |
| Week 10 full grid incomplete | Drop to the primary or minimum tier; keep the core comparison |
| Week 11 no result supports H1-H6 | Write the negative-result paper; do not fabricate |

## 4. Tier choice (record before sweep)

| Tier | Datasets | Models | Seeds | Runs | Purpose |
|---|---|---|---|---|---|
| Minimum publishable | TLC, MovieLens | LightGBM, linear/logistic | 3 | 888 | Workshop paper |
| Primary | TLC, MovieLens, Retail | LightGBM, linear/logistic | 3 | 1,332 | Main results |
| Full | TLC, MovieLens, Retail | LightGBM, linear/logistic, MLP | 5 | 3,330 | Journal robustness |

## 4b. Law success criteria

The law is the headline only if these gates pass. Each failure has a written fallback; none of them kills the measurement study.

| Gate | Pass | Fail action |
|---|---|---|
| H5 collapse | Corruption-only MAE at least 10% lower than the lookup table on held-out defects | Drop the law from the headline; keep the measurement study |
| H5 identity | Defect identity adds less than 10% MAE | Report the law as incomplete; do not claim a collapse |
| H5 transfer | R2 at least 0.5 on MovieLens and Retail without refitting | Report domain dependence; scope the law to TLC |
| H6 ranking | Spearman at least 0.3 and AUC at least 0.7 for the silence index | Report detectability as defect-specific; drop the index from the headline |
| H6 contrast | Alpha-dominant recall at least 10 points lower than beta/gamma-dominant | Same as above |
| Annotation sanity | Clean/clean pairs give alpha, beta, and gamma near zero | Fix the matcher before trusting any law result |

The law is evaluated after the 240-run TLC single-defect grid (week 3 extension) and again after the final grid. The first evaluation uses alpha and gamma; beta is added at week 6, and the full vector is only claimed after week 10.

## 5. Weekly checklist

- [ ] Deliverable committed and tagged.
- [ ] Tests pass in CI.
- [ ] Experiment configs hashed and recorded.
- [ ] Results table updated, including nulls.
- [ ] Deviations logged in `docs/PREREGISTRATION.md`.
- [ ] One paragraph added to the paper draft or lab notebook.

## 6. Definition of done

- `make data`, `make audit`, `make baseline`, `make pilot`, `make experiment`, `make reproduce`, `make demo` all work from a clean clone.
- The full grid is reproducible within numerical tolerance.
- Every figure is generated from a config, not hand-edited.
- The paper draft cites only verified sources.
- The artifact has a DOI and a README that a stranger can follow.
- Every run record carries alpha, beta, gamma, and the silence index.
- R6 and R7 are generated from the run table, including any failed law fit.
- The model card documents intended use and limitations.

## 7. Buffer plan

Weeks 13-16 are not free time. Use them for:

1. A fourth real dataset (UCI Bike Sharing) if reviewers ask for external validity beyond transport, media, and retail.
2. A journal extension with a deeper related-work section.
3. Rebuttals and camera-ready preparation.
4. A public demo deployment on a free tier with aggregated data only.

If everything finishes early, stop. Do not add scope to look impressive.

## 8. Revised priority rule

The roadmap is evidence-first. Weeks 2-7 are the core research program; weeks 8-12 are validation, packaging, and publication support. A later technology milestone cannot compensate for a missing experiment or an unverified claim. See `docs/REPRODUCIBILITY.md` and `docs/SIMULATOR_VALIDATION.md`.

## 9. Phase 2: top-tier extension (months 4-9)

The twelve-week plan produces a workshop paper and a defensible measurement study. The law turns it into a top-tier submission only if it survives the full grid. Phase 2 is conditional on the week 7 gates.

| Month | Work | Exit criterion |
|---|---|---|
| 4 | Full grid at the chosen tier; law refit with alpha, beta, and gamma; leave-one-defect-out at full scale | R6 complete; H5 verdict written |
| 5 | TLC-to-MovieLens and TLC-to-Retail transfer; domain-interaction analysis | R6 transfer table; transfer gap reported |
| 6 | Proxy alpha: estimate decision displacement from metadata and monitored signals, report estimation error | A deployable version of the law with a measured gap from the oracle |
| 7 | Robustness: threshold sensitivity, natural-defect exclusion, alternative model families, simulator validation | Every headline number has a sensitivity check |
| 8 | Theory write-up: why alpha dominates, when the law should fail, relation to existing drift theory | Section 5 of the paper is a mechanism, not a curve fit |
| 9 | Top-tier submission package: SIGMOD/VLDB/ICDE 2028 or NeurIPS D&B 2027; arXiv and Zenodo | Submitted, artifact DOI, preprint posted |

If the law fails at month 4, stop Phase 2 and submit the measurement study to DEEM, DSAA, or JDIQ. Do not spend months rescuing a failed law with new predictors; that is the p-hacking path the preregistration forbids.
