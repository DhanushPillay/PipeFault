# Literature matrix

Verified on 2026-10-28 against Crossref `works/{doi}` and OpenAlex
`works/doi:{doi}`. Pipeline-debugging works were added on 2026-11-04 and
checked against both APIs. Every DOI below resolved to the title and first
author shown. Two citations in `docs/RESEARCH.md` were corrected after this
check: the ASE 2022 leakage DOI belongs to Yang et al., not Kapoor and
Narayanan, and the Wu and Keogh DOI was wrong. Preprints are listed separately
and are not counted toward the 30-paper target.

**Coverage:** 43 DOI-verified papers, plus 5 arXiv-only sources.

## How to read this

- **Claim**: what the paper asserts, not what this project asserts.
- **Method**: study design or system.
- **Data**: evidence base.
- **Metric**: what the paper measures.
- **Threat**: why the paper does not already answer PipeFault's question.

## 1. Data quality and ML performance

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Sambasivan et al., `10.1145/3411764.3445518` | CHI 2021 | Data issues compound into cascades; 92% of practitioners reported them | Interviews with 53 practitioners in high-stakes AI | India, East and West Africa | Prevalence and themes | Qualitative; no controlled pipeline, labels, or lead time |
| Mohammed et al., `10.1016/j.is.2025.102549` | Information Systems 2025 | Data-quality dimensions degrade tabular ML at different rates | Controlled experiments across DQ dimensions, algorithms, datasets | 10 tabular datasets, 19 algorithms (as reported) | Predictive performance | Static tables, single defects, no streaming or event time |
| Gupta et al., `10.1145/3447548.3470817` | KDD 2021 tutorial | DQ assessment must precede ML; errors enter at collection, aggregation, annotation | Tutorial and framework | — | — | No benchmark, no defect injection |
| Jain et al., `10.1145/3394486.3406477` | KDD 2020 tutorial | Model performance is upper-bounded by data quality | Overview and taxonomy | — | — | Position/tutorial; no measurement |
| Chai et al., `10.1109/TKDE.2022.3148237` | TKDE 2022 | Data management for ML spans acquisition, cleaning, integration, debugging | Survey | — | — | No controlled operator-level study |
| Whang et al., `10.1007/s00778-022-00775-9` | VLDB J. 2023 | Data collection and quality are core data-centric AI bottlenecks | Survey | Deep-learning lifecycle | — | No pipeline-operator measurement |
| Roh et al., `10.1109/TKDE.2019.2946162` | TKDE 2021 | Data collection, labeling, and quality are the main ML bottleneck | Survey | — | — | No defect taxonomy or degradation measurement |
| Chu et al., `10.1145/2882903.2912574` | SIGMOD 2016 tutorial | Cleaning problems form a taxonomy: constraints, dedup, transformations | Survey/tutorial | — | — | Repairs static tables; no downstream ML or streaming |
| Rekatsinas et al., `10.14778/3137628.3137631` | PVLDB 2017 | Holistic probabilistic repair beats isolated cleaning | Probabilistic inference over constraints and statistics | Real dirty tables | Repair accuracy | Static repair, no pipeline operators or lead time |

## 2. Leakage and evaluation validity

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Kapoor and Narayanan, `10.1016/j.patter.2023.100804` | Patterns 2023 | Leakage affects 294 papers in 17 fields and inflates results | Literature survey and taxonomy | 17 fields | Prevalence, effect on reported accuracy | Leakage is a different failure mode; no operator injection |
| Yang et al., `10.1145/3551349.3556918` | ASE 2022 | Static analysis can detect common leakage in notebooks | Static analysis tool | Jupyter notebooks | Leakage detection | Code-level leakage, not runtime data defects |
| Mishra et al., `10.1371/journal.pone.0340167` | PLOS ONE 2026 | Temporal leakage inflates build prediction; a taxonomy can detect and prevent it | Dual-platform empirical validation | Build-prediction data | Inflated performance | Leakage-specific; no streaming operator study |

## 3. Fault injection and benchmarks

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Rahal et al., `10.1007/978-3-031-49252-5_5` | ECBS 2023 | Fault injection can test ML data suitability and performance | Mutation/fault-injection framework | ML data suitability case study | Model performance under faults | One mutator at a time, no compounding, no lead time |
| Nurminen et al., `10.1109/ISSREW.2019.00087` | ISSREW 2019 | Configurable data-fault emulation exposes ML sensitivity | dpEmu framework with pluggable fault models | Text, time series, video | System behavior under faults | Single faults, no pipeline semantics, no lead-time evaluation |

## 4. Production ML, observability, and operations

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Shankar and Parameswaran, `10.14778/3565838.3565853` | PVLDB 2022 | ML observability must detect, diagnose, and react without real-time labels | Vision and system sketch | — | — | No benchmark or controlled defects |
| Shankar et al., `10.1145/3653697` | CSCW 2024 | Engineers rely on intuition and post-hoc debugging; production behavior is unknowable in advance | Ethnographic interviews with 18 MLEs | Production teams | Themes and practices | Qualitative; no measurement |
| Karlaš et al., `10.1145/3722212.3725636` | SIGMOD 2025 tutorial | Data errors traverse pipeline stages; teams must identify, debug, and learn from them | Tutorial | — | — | No controlled benchmark |
| Polyzotis et al., `10.1145/3035918.3054782` | SIGMOD 2017 tutorial | Production ML raises validation, cleaning, and enrichment challenges | Experience-based tutorial | — | — | No empirical defect study |
| Breck et al., `10.1109/BigData.2017.8258038` | IEEE Big Data 2017 | 28 tests make production readiness measurable | Rubric | — | Test pass rate | Checklist; not defect-specific degradation |
| Baylor et al., `10.1145/3097983.3098021` | KDD 2017 | An end-to-end platform can orchestrate validation, training, and serving | TFX system | Production pipelines | System capability | Infrastructure paper; no defect measurement |
| Kreuzberger et al., `10.1109/ACCESS.2023.3262138` | IEEE Access 2023 | MLOps needs an architecture spanning CI, CD, and continuous training | Survey and reference architecture | — | — | No empirical defect study |
| Paleyes et al., `10.1145/3533378` | ACM CSUR 2022 | Deployment challenges recur across published case studies | Survey of case studies | Published deployments | Themes | Qualitative; no controlled injection |

## 5. Concept drift and streaming ML

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Gama et al., `10.1145/2523813` | ACM CSUR 2014 | Concept drift requires detection and adaptation | Survey | — | — | Drift is not a pipeline data defect; no operator attribution |
| Lu et al., `10.1109/TKDE.2018.2876857` | TKDE 2018 | Drift learning needs detection, understanding, and adaptation | Review | — | — | Same; no defect injection |
| Lukats et al., `10.1007/s41060-024-00620-y` | IJDSA 2024 | Unsupervised drift detectors can work without labels, but rankings vary | Benchmark and survey | Real-world data streams | Detection quality | Detects drift, not defect cause or lead time to damage |
| Gomes et al., `10.1145/3373464.3373470` | SIGKDD Explorations 2019 | Streaming ML needs incremental learning and drift handling | Survey | — | — | No data-quality defect study |

## 6. Event time and stream processing

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Akidau et al., `10.14778/2824032.2824076` | PVLDB 2015 | Event-time windows and watermarks separate correctness from latency | Dataflow model and implementation | Unbounded datasets | Latency/correctness | Semantics only; no ML impact |
| Akidau et al., `10.14778/2536222.2536229` | PVLDB 2013 | Low-latency streaming needs watermarks, persistent state, and exactly-once processing | MillWheel system | Google production streams | System guarantees | No ML quality measurement |
| Armbrust et al., `10.1145/3183713.3190664` | SIGMOD 2018 | A declarative API can incrementalize a static query for streaming | Structured Streaming system | Spark workloads | System capability | No defect study |
| Murray et al., `10.1145/2517349.2522738` | SOSP 2013 | Timely dataflow unifies batch, streaming, and iterative computation | Naiad system | Dataflow programs | Throughput/latency | No ML or data quality |
| Zaharia et al., `10.1145/2934664` | CACM 2016 | One engine can unify batch, streaming, and interactive workloads | Apache Spark system | Production workloads | System capability | No defect study |

## 7. Freshness, staleness, and adjacent negative results

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Wooders et al., `10.14778/3632093.3632116` | PVLDB 17, 2023 | Accuracy-aware scheduling of feature maintenance beats one-size-fits-all policies | RALF scheduler and evaluation | Feature-store workloads | Accuracy versus maintenance cost | Freshness only; no compounding or lead-time evaluation |
| Wang et al., `10.24963/ijcai.2023/261` | IJCAI 2023 | Feature staleness degrades CTR; replay and regularization mitigate it | FeSAIL incremental learning | CTR benchmarks | AUC | One freshness mechanism, not an operator-defect benchmark |
| Wu and Keogh, `10.1109/TKDE.2021.3112126` | TKDE 2023 | Most anomaly-detection benchmark labels are flawed; reported progress is illusory | Label audit and triviality analysis | Public AD benchmarks | Label error and triviality rates | Benchmark critique; a warning to audit our own labels |
| Kothapalli et al., `10.1145/3770855.3818354` | KDD 2026 | Training-serving skew comes from stale data, delayed labels, precision, and covariate shift | Industrial case study and metrics | Ad-auction models | Skew and model quality | One company, staleness-specific, no controlled operator grid |
| Sukprasert et al., `10.1145/3627703.3650079` | EuroSys 2024 | Carbon-aware temporal and spatial shifting has limited practical benefit | Trace-based upper-bound analysis | Cloud workload traces | Carbon reduction | Scope control; not data quality |
| Shahmirzadi et al., `10.1007/s00607-026-01718-w` | Computing 2026 | Hybrid ML predicts task failure on cluster traces | Supervised ML on traces | Google cluster traces | Failure-prediction accuracy | Infrastructure failure, not data defects |

## 8. Pipeline debugging and attribution

| Work | Venue | Claim | Method | Data | Metric | Threat to this project |
|---|---|---|---|---|---|---|
| Grafberger et al., `10.1145/3448016.3452759` | SIGMOD 2021 | Distribution errors in ML pipelines can be detected and explained at the operator level | MLINSPECT debugger | ML pipelines | Distribution violations | Debugging focus; no damage law, severity sweep, or lead time |
| Grafberger et al., `10.1007/s00778-021-00726-w` | VLDB J. 2022 | Distribution debugging can be framed as constraints over pipeline operators | Constraint-based debugging | ML pipelines | Violation detection | Detects violations; no compounding or detectability prediction |
| Rezig et al., `10.14778/3415478.3415527` | PVLDB 2020 | Fine-grained lineage supports debugging data science pipelines | Dagger lineage system | Large-scale pipelines | Debugging capability | Requires lineage; no injection, degradation, or early warning |
| Lourenço et al., `10.1145/3318464.3384692` | SIGMOD 2020 | Pipeline debugging can search the parameter space to explain failures | BugDoc system | Computational pipelines | Failure explanation | Single-pipeline debugging; no streaming monitor evaluation |
| Zhang et al., `10.1145/3702992` | TOSEM 2025 | AutoML pipeline faults can be localized and repaired | DREAM | AutoML pipelines | Fault localization and repair | Code and configuration faults, not operator data defects |
| Lazzaro et al., `10.14778/3827998.3828102` | PVLDB 2026 | Provenance plus explanations support interactive pipeline debugging | PROXAI | ML pipelines | Debugging quality | Interactive diagnosis; no quantitative damage law |

These systems answer "where did it break?" They do not answer "how much damage will this defect do, and will a monitor see it before labels arrive?" That distinction is the space PipeFault occupies.

## 9. Preprints and non-DOI sources

Not counted toward the 30-paper target. Verified against the arXiv API on
2026-10-28.

| Work | ID | Claim | Threat to this project |
|---|---|---|---|
| Garg et al., ATC | arXiv:2201.04234 | Unlabeled test data can estimate OOD accuracy | No pipeline metadata, no diagnosis |
| Wild-Time | arXiv:2211.14238 | Distribution shift over time needs a dedicated benchmark | Shift benchmark, not operator defects |
| Back2Future | arXiv:2106.04420 | Backfill dynamics can improve real-time prediction | Revision-aware forecasting, not defect injection |
| Budach et al. | arXiv:2207.14529 | Data quality dimensions affect tabular ML performance | Static tables, no streaming or lead time |
| Zhou et al. | arXiv:2406.19614 | Surveys DQ dimensions and tools for ML | Survey; no controlled pipeline study |

## 10. Synthesis

Three claims are well covered: static data quality affects ML performance;
leakage inflates evaluation; event-time systems provide watermarks and
exactly-once semantics. Pipeline debugging is also covered: MLINSPECT, Dagger,
BugDoc, DREAM, and PROXAI locate and explain failures after they happen.

The gap is the intersection:

1. Defects are injected at the operator level (join, watermark, SCD, schema),
   not only as corrupted cells.
2. Severities are controlled so single and compounding effects are comparable.
3. Observability metadata is evaluated on lead time before labels arrive,
   against ATC and static thresholds.
4. A low-dimensional corruption vector predicts both damage and detectability,
   including for defects the model was not fitted on.

No paper above measures all four. The debugging systems answer where a failure
came from; none predicts how much damage an operator defect will cause or
whether monitors will see it before labels do. That is the claim the experiment
must earn.
