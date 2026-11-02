# Publication strategy

Dates change. Verify every deadline on the official call for papers before planning around it. The dates below were checked in October 2026.

## 0. Working title and abstract

**Title:** PipeFault: Measuring Compounding Operator-Level Data Defects and Label-Free Early Warning in Streaming ML Pipelines

**Alternative:** When Data Pipelines Fail Silently: A Controlled Study of Compounding Operator Defects and Label-Free Early Warning

**Abstract draft:**

> Production ML pipelines often fail without an error. A join fans out, a dimension arrives late, a watermark drops events, or a schema change coerces a type. The job succeeds and model quality degrades silently. Existing studies inject data-quality defects into static tables, but they do not model pipeline operators, event time, compounding defects, or the delay before labels reveal damage. We present PipeFault, a reproducible fault-injection harness for streaming ML pipelines, and a controlled measurement study on three real public datasets: NYC taxi trips, Olist e-commerce orders, and UCI Online Retail II. We define eight operator-level defects, inject them singly, in pairs, and in selected triples at controlled severity, and measure degradation, interaction effects, and detection latency. We then test whether cheap observability metadata predicts degradation before labels arrive, compared with Average Thresholded Confidence and static thresholds. The study reports negative results and domain dependence where they occur. Code, configs, and run artifacts are released for reproduction.

## 1. Target venues

| Venue | Type | Expected deadline | Indexing | Cost | Fit | Risk |
|---|---|---|---|---|---|---|
| DEEM 2027, workshop at SIGMOD/PODS | Workshop | ~March 2027 (DEEM 2026 submissions were March 2026; workshop 5 June 2026) | ACM DL, not Scopus | Registration fee; verify | Excellent: data management for end-to-end ML | Workshop, not indexed |
| IEEE DSAA 2027 | Conference | ~May 2027 (DSAA 2026 was 6–9 Oct, New Delhi) | IEEE, Scopus | Registration | Good | Call not published as of Oct 2026 |
| IEEE BigData 2027 | Conference | ~August 2027 (2026 deadline was 21 Aug) | IEEE, Scopus | Full registration for accepted papers, not student rate | Good | 18% acceptance in 2025 |
| ACM JDIQ | Journal | Rolling | Scopus | APC US$1,450 no member / US$950 member; lower-middle-income US$725 / US$475 | Excellent: empirical data quality | Slow review |
| IEEE Access | Journal | Rolling | SCIE/Scopus | APC US$2,160 plus taxes | Fallback | Cost |
| MSR 2028 | Conference | ~October 2027 | ACM, Scopus | Registration | Only for the SchemaMiner backup | Wrong cycle for this project |

Recommended sequence: DEEM 2027 first, then DSAA 2027 or JDIQ extension, with BigData 2027 as backup. Do not pay for IEEE Access unless funding exists and a fast journal line is required.

## 2. Paper structure

1. **Introduction.** Silent pipeline defects, Data Cascades, observability gap, contributions.
2. **Related work.** DQ to ML, drift, freshness, pipeline debugging, label-free estimation.
3. **Taxonomy and threat model.** Eight defects, operator mapping, severity definition.
4. **PipeFault harness.** Injector, event-time simulator, observability signals, reproducibility.
5. **Experimental setup.** Datasets, models, conditions, metrics, statistics.
6. **Results.** R1 clean baseline, R2 dose-response, R3 interactions, R4 early warning, R5 ablations.
7. **Discussion.** Implications for data engineers; when observability fails; blind spots.
8. **Threats to validity.**
9. **Conclusion.**
10. **Artifact appendix.** DOI, commands, hardware, runtime.

Target length: 8–10 pages for DEEM or DSAA, 10 pages for BigData, journal length for JDIQ.

## 3. Figures and tables

| Item | Content | Claim it supports |
|---|---|---|
| Fig. 1 | Architecture | The harness is a real system |
| Fig. 2 | Taxonomy diagram | Defects map to operators, not datasets |
| Fig. 3 | Dose-response curves | RQ1, H1 |
| Fig. 4 | Interaction heatmap | RQ2, H2 |
| Fig. 5 | Lead-time vs false-alarm tradeoff | RQ3, H3 |
| Table 1 | Related-work comparison | Novelty positioning |
| Table 2 | Datasets, tasks, licenses, splits | Reproducibility |
| Table 2b | Natural-defect audit and calibrated severity | Construct validity |
| Table 3 | Single-defect results | RQ1 |
| Table 4 | Compounding results | RQ2 |
| Table 5 | Early-warning comparison | RQ3 |
| Table 6 | Ablations | RQ4 |
| Table 7 | Compute and runtime | Reproducibility |

## 4. Related-work positioning

| Work | Claim | Limitation | This project |
|---|---|---|---|
| Mohammed et al. 2025 | DQ dimensions degrade ML | Dataset-level, static, single defects | Operator-level, streaming, compounding, lead time |
| Dapaah & Grabowski 2025 | DQ issues co-occur | Software defect prediction only | General pipelines plus observability |
| Shankar & Parameswaran 2022 | Observability needs detect/diagnose/react | Vision, no benchmark | Controlled benchmark |
| FIUL-Data, ECBS 2023 | Fault injection tests ML resilience | One fault at a time, no lead time | All-pairs compounding plus early warning |
| dpEmu, ISSREW 2019 | Data fault emulation for ML systems | Single faults, no lead time | Compounding plus observability |
| RALF 2024 | Freshness affects accuracy | Freshness only | Broader operator taxonomy |
| Garg et al., ICLR 2022 | ATC predicts OOD accuracy | No pipeline metadata | Operator-aware features versus ATC |
| Karlaš et al., SIGMOD Companion 2025 | Data errors propagate across pipeline stages | Tutorial, no controlled benchmark | Controlled benchmark with lead time |

## 5. Claims checklist

Do not write a claim until the corresponding evidence exists.

- [ ] H1 supported by dose-response across at least two datasets and three seeds.
- [ ] Silent defects shown to evade PSI/KS at a stated threshold and recall.
- [ ] H2 supported by additive RERI with 95% CI, or reported as a null.

## 6. Evidence-first paper boundary

The paper should make a modest claim that the experiments can support:

> Under controlled real-record treatments, operator-level defects can produce
> different model degradation and monitoring signatures, and their detectability
> depends on defect type, severity, dataset, and the time at which labels arrive.

The paper should not claim universal defect coverage, production readiness, or
that observability replaces labels. The minimum evidence package is a TLC pilot
with four defects, paired clean controls, three seeds, frozen thresholds,
confidence intervals, and false-alarm and lead-time results. Olist, Retail,
Spark validation, and the demo strengthen the artifact but are not substitutes
for this evidence.

```mermaid
flowchart TD
	A[Research question] --> B[Pre-registered mechanism]
	B --> C[Paired controlled run]
	C --> D[Metric and confidence interval]
	D --> E[Claim in paper]
	E --> F[Limitation and threat]
```

## 7. Hardware and reproducibility statement

The primary study is designed to run on a single workstation with 16 GB RAM.
The expected bottlenecks are wall-clock time and disk space, not GPU memory.
Monthly/chunked processing and one or two workers are the default. The RTX 4060
is optional because CPU LightGBM and linear models are sufficient for the first
paper. Any cloud, distributed engine, or GPU result is an extension and must be
reported separately from the local reference results.
- [ ] H3 supported by MAE reduction on at least one classification dataset and lead time at a fixed false-alarm rate.
- [ ] H4 supported by a mixed-effects model, or dropped.
- [ ] Ablations show which signal families matter.
- [ ] Simulator validated against Spark, or the streaming claim removed.
- [ ] All conditions reported, including nulls.
- [ ] Limitations section names the construct, external, and simulator threats.

## 6. Ethics and reproducibility

- Public data only. No PII. Olist review text is not used at all; only the numeric score.
- Olist is CC BY-NC-SA 4.0: non-commercial, share-alike. Do not redistribute raw data.
- TLC is NYC Terms of Use. Ship download scripts, not raw files.
- Online Retail II is CC BY 4.0. Attribution required; raw data may be redistributed, but the artifact uses scripts for consistency.
- Code under MIT. Artifact and docs under CC BY 4.0.
- Model card: intended use, limitations, and an explicit warning that this is a research prototype.
- Pre-registration committed before the full sweep.
- Negative results reported, not hidden.
- Artifact on Zenodo with a DOI; arXiv preprint after submission.

## 7. Predatory venue checks

Red flags:

- Guaranteed acceptance or an acceptance promise in email.
- Review in under two weeks.
- Compulsory fees for a special issue.
- Unclear or unnamed reviewers.
- Indexing claims you cannot verify on the Scopus source list.
- Spam solicitation after a conference submission.

Checks:

- Think.Check.Submit.: `https://thinkchecksubmit.org`
- Scopus source list.
- IEEE and ACM digital libraries for the venue.
- Ask a faculty member before paying any fee.

Do not target venues that publish quickly for a fee. Some low-quality venues publish fault-injection papers with broad claims and no artifact; do not cite them as serious baselines and do not submit there.

## 8. Submission checklist

- [ ] Official CFP and deadline verified on the venue site.
- [ ] Dataset licenses and attribution checked for every table and figure.
- [ ] Page limit and template followed.
- [ ] Anonymization rules followed, if double-blind.
- [ ] All references verified with DOI or URL.
- [ ] Artifact DOI available.
- [ ] Ethics statement included.
- [ ] Reproducibility appendix included.
- [ ] Advisor or senior reviewer read the draft.
- [ ] Registration cost understood before submission.
