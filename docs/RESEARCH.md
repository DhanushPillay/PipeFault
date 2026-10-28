# Research context

This document records why the project exists, what is already published, and what is not claimed. Update it as the literature review grows.

## 1. Problem

Production ML pipelines fail silently. A join duplicates rows, a dimension arrives late, a watermark discards events, or a schema change coerces a type. The job succeeds and the model degrades without an alarm. The delay between cause and observable damage is the core difficulty: labels arrive late, dashboards monitor infrastructure rather than semantics, and engineers cannot tell which pipeline component is responsible.

## 2. Motivation

- Data Cascades reports 92% prevalence of compounding data issues in high-stakes AI, with delayed and invisible effects (Sambasivan et al., CHI 2021, DOI 10.1145/3411764.3445518).
- Observability for production ML is an explicit open agenda: detect, diagnose, react, under missing real-time labels (Shankar & Parameswaran, PVLDB 2022, DOI 10.14778/3565838.3565853).
- Practitioners still operationalize ML by intuition and post-hoc debugging (Shankar et al., CSCW 2024, DOI 10.1145/3653697).
- The data-management community treats error propagation through pipeline steps as an open challenge (Karlaš, Salimi, Schelter, SIGMOD Companion 2025, DOI 10.1145/3722212.3725636).

## 3. What is already closed

| Area | Closest work | Status |
|---|---|---|
| Dataset-level DQ to ML performance | Mohammed et al., Information Systems 2025, DOI 10.1016/j.is.2025.102549 | Closed for single defects on static tables |
| Co-occurring DQ issues | Dapaah & Grabowski, arXiv:2512.17460 (preprint) | Partially open; only software defect prediction |
| Data leakage | Kapoor & Narayanan, Patterns 2023; ASE 2022, DOI 10.1145/3551349.3556918; PLOS ONE 2026, DOI 10.1371/journal.pone.0340167 | Closed |
| Concept drift benchmarks | Wild-Time, NeurIPS 2022; Lukats et al., IJDSA 2024, DOI 10.1007/s41060-024-00620-y | Closed |
| Feature freshness | RALF, PVLDB 17 (2024); FeSAIL, IJCAI 2023; KDD 2026, DOI 10.1145/3770855.3818354; arXiv:2610.02259 | Closing fast |
| Lakehouse compaction | AutoComp, SIGMOD Companion 2025; arXiv:2608.08639 | Closed, with a near-negative result |
| Carbon-aware scheduling | EuroSys 2024, DOI 10.1145/3627703.3650079; SIGCOMM 2025; LinTS, IEEE CLOUD 2025 | Closed, with a negative result |
| Cluster failure prediction | FiCloud 2023; Computing 2026, DOI 10.1007/s00607-026-01718-w | Closed and compute-heavy |
| Time-series anomaly detection | Wu & Keogh, IEEE TKDE 2023; Baldán et al., Expert Systems 2025 | Closed |
| Backfill and data revisions | Back2Future, ICLR 2022, arXiv:2106.04420 | Open but narrow |

## 4. The gap

Existing work injects errors at the dataset level into static tables, or studies one operator in isolation, usually freshness. Three things are missing together:

1. **Operator-level defects** tied to pipeline semantics: joins, watermarks, SCD versions, schema coercion.
2. **Compounding interactions** measured under controlled severity in a streaming setting.
3. **Lead time**: whether cheap observability metadata predicts damage before labels arrive, evaluated against label-free accuracy estimators.

The gap is a measurement gap, not an algorithm gap. State that plainly in the paper.

## 5. Contributions

1. An 8-defect taxonomy mapped to pipeline operators, with injection mechanics and expected symptoms.
2. A reproducible harness with a deterministic event-time simulator and a config-driven injector.
3. A measurement study of single and compounding defects across three real domains: transport (TLC), marketplace (Olist), and retail (Online Retail II).
4. An early-warning evaluation against ATC and static thresholds, reporting MAE, lead time, and false-alarm rate.
5. An open artifact: code, configs, run results, and a reproducibility package.

## 6. What is not claimed

- Not a new algorithm. The predictor is gradient boosting on engineered signals.
- Not a production monitor. The harness is an experimental instrument.
- Not a claim that observability beats labels in general. It tests specific defects under specific conditions.
- Not a claim of universal defect coverage. Eight defects, three real domains.
- Not a claim that the taxonomy is complete. It covers common operators, not every failure mode.

## 7. Adjacent work to cite and differentiate

| Work | What it does | Why it is not this project |
|---|---|---|
| Mohammed et al. 2025 | Six DQ dimensions, 19 algorithms, 10 tabular datasets | Dataset-level, static, single defects, no lead time |
| Dapaah & Grabowski 2025 | Co-occurring DQ issues in software defect prediction | SDP domain, DQ dimensions, no pipeline operators |
| FIUL-Data, ECBS 2023, DOI 10.1007/978-3-031-49252-5_5; arXiv:2309.11274 | Fault injection for ML data suitability | One mutator at a time, analytical chemistry, no compounding |
| dpEmu, ISSRE Workshops 2019, DOI 10.1109/ISSREW.2019.00087 | Data fault emulation for ML systems | Single faults, no lead-time evaluation |
| RALF, PVLDB 2024 | Feature store maintenance under budget | Freshness only, scheduling focus |
| Garg et al., ICLR 2022, arXiv:2201.04234 | ATC for label-free OOD accuracy | No pipeline metadata, no diagnosis |
| Karlaš, Salimi, Schelter, SIGMOD Companion 2025, DOI 10.1145/3722212.3725636 | Tutorial on data errors across pipeline stages | No controlled benchmark, no lead-time evaluation |
| Shankar & Parameswaran 2022 | Observability vision | No benchmark |

## 8. Open questions to resolve during the build

- Does the severity definition transfer across defects, or does each defect need its own scale?
- Does join topology (star versus snowflake, one-to-one versus one-to-many) change the interaction magnitude?
- Is the 90-day label window in Online Retail II stable across the 2011 test period, or does right-censoring bias the last quarter?
- Are interaction effects stable across datasets, or domain-specific?
- Does operator-aware metadata beat generic drift signals on silent defects only, or also on volume defects?
- How much does the event-time simulator diverge from Spark Structured Streaming?
- Is the predictor useful at the batch granularity a real team would use?

## 9. Evidence standard

- Prefer peer-reviewed sources. Mark preprints explicitly.
- Record DOI or URL for every citation.
- Do not quote a number from an abstract without checking the full text.
- Keep a literature matrix with columns: claim, method, dataset, metric, limitation, threat to this project.
