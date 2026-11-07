# Datasets

Three real public datasets. No synthetic rows, no semi-synthetic control, no generated customers or trips. The only constructed element is the defect treatment applied to real records; the clean run is the reference. This is standard fault injection, not fabricated data.

## 1. Summary

| Dataset | Role | Source | License | Size | Dates | Task | Target |
|---|---|---|---|---|---|---|---|
| NYC TLC yellow taxi, 2024 | Primary; large, event-time, static + time-varying dimension | NYC TLC / AWS Open Data | NYC Terms of Use | 12 monthly files; 800k sample | Jan–Dec 2024 | Pre-trip ETA regression | Trip duration (min) |
| MovieLens 32M | Multi-table joins; media classification | GroupLens Research | GroupLens research license | 32,000,204 ratings; 2,000,072 tags; 87,585 movies; 200,948 users | 1995–2023 | High-rating classification | `rating >= 4` |
| UCI Online Retail II | Single-table retail; long horizon; repeat-purchase label | UCI ML Repository, DOI 10.24432/C5CG6D | CC BY 4.0 | 1,067,371 lines | Dec 2009–Dec 2011 | Repeat purchase within 90 days | Binary |

All three are downloadable without credentials or a subscription.

## 2. NYC TLC yellow taxi

### Source and files

- Landing page: `https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page`
- Monthly Parquet pattern: `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-MM.parquet` for `MM` in `01`–`12`. Some links on the page carry a trailing `%20`; strip it.
- Zone lookup: `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv`
- Data dictionary: `https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf`
- License: NYC Terms of Use, `https://www.nyc.gov/home/terms-of-use.page`. Download by script; do not commit raw files.

### Fields (2024 yellow)

`VendorID`, `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `passenger_count`, `trip_distance`, `RatecodeID`, `store_and_fwd_flag`, `PULocationID`, `DOLocationID`, `payment_type`, `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount`, `congestion_surcharge`, `Airport_fee`.

2025+ adds `cbd_congestion_fee`. Pin the 2024 schema; do not mix years without an explicit schema map.

Verified on the full 2024 year (local audit): 41,169,720 rows; 526,866 invalid durations; 776,305 non-positive distances; 731,024 negative fares; 146,201 invalid pickup zones; 370,258 invalid dropoff zones; 401,354 zero-passenger trips; 4,091,232 nulls each in `passenger_count`, `RatecodeID`, `store_and_fwd_flag`, `congestion_surcharge`, and `Airport_fee`; 8 duplicate rows. Pickup timestamps span 2002-12-31 to 2026-06-26, so out-of-range event times are a real defect the simulator must handle.

### Task and prediction point

Predict trip duration at pickup. Label = `(tpep_dropoff_datetime - tpep_pickup_datetime)` in minutes.

Allowed features:

- `VendorID`, pickup hour, day of week, month, `passenger_count`.
- `PULocationID`, `DOLocationID`.
- As-of zone statistics: average duration and trip count per pickup zone per day, computed only from trips before the current event time. Do not use average fare; it adds a post-trip-derived feature without a clear benefit.
- Optional: NOAA hourly weather for New York, joined by timestamp. Public domain. Add only if it improves the clean baseline; report it as a separate feature set.

Excluded because they are post-pickup or label-derived:

- `tpep_dropoff_datetime`, `trip_distance`, `payment_type`, `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount`, `congestion_surcharge`, `Airport_fee`, `store_and_fwd_flag`.
- `RatecodeID`: assigned during the trip and not reliably known at pickup. Exclude it rather than argue about the timing.

`trip_distance` is recorded at drop-off and is not known at pickup. Including it would leak the label.

### Cleaning

- Pickup and dropoff inside 2024. Drop rows whose pickup or dropoff timestamp falls outside the file's month, so monthly partitions cannot leak across splits.
- Duration between 1 and 180 minutes. Drop negative and zero durations.
- `trip_distance > 0`.
- `fare_amount >= 0`, `total_amount >= 0`.
- `PULocationID` and `DOLocationID` in 1–263. Drop 264 (Unknown) and 265 (N/A) for join experiments.
- `passenger_count` between 0 and 6. Keep 0 as a separate category; do not silently impute.
- Do not clip outliers silently. Record the count and the rule.

### Time-varying dimension

Daily zone statistics with `effective_from` and `effective_to`:

- `zone_id`, `date`, `avg_duration`, `avg_fare`, `trip_count`, `effective_from`, `effective_to`.

Computed with a one-day lag from prior trips only. The as-of join uses the version effective at the trip's pickup time. The faulty variant uses `is_latest = true`.

### Split and sample

- Train: Jan–Jun 2024, 500k trips.
- Validation: Jul–Sep 2024, 150k trips.
- Test: Oct–Dec 2024, 150k trips.
- 1-day embargo between splits.
- Sample by deterministic hash of a stable trip key, not by random row order. Keep the monthly distribution.
- Cap each monthly partition before concatenation to bound memory, then enforce the exact split size with a deterministic hash sample.

### Clean reference result

Seed 42, 500k/150k/150k rows, LightGBM: validation RMSE 6.743, MAE 4.335, R2 0.763; test RMSE 7.201, MAE 4.613, R2 0.740. The test RMSE across seeds 42-44 is 7.19 +/- 0.01 (mean +/- sample SD). These are the clean-reference numbers for defect comparisons.

### Natural defects to audit

Negative fares, zero distance, durations outside 1–180 minutes, timestamps outside the file month, unknown zones 264/265, `passenger_count` above 6, `RateCodeID = 99`, duplicate rows. These calibrate the injectors; they are not the treatment.

## 3. MovieLens 32M

### Source and files

- Landing page: `https://grouplens.org/datasets/movielens/32m/`
- Archive: `https://files.grouplens.org/datasets/movielens/ml-32m.zip` (239 MB; 238,950,008 bytes locally).
- README and license: `https://files.grouplens.org/datasets/movielens/ml-32m-README.html`
- License: GroupLens research license. Research use is allowed; commercial or revenue-bearing use requires permission; redistribution is allowed only under the same terms. Cite Harper & Konstan 2015, DOI `10.1145/2827872`. Raw files are not committed.
- Four UTF-8 CSVs with one header row:

| File | Rows | Columns | MD5 |
|---|---:|---|---|
| `ratings.csv` | 32,000,204 | `userId`, `movieId`, `rating`, `timestamp` | `cf12b74f9ad4b94a011f079e26d4270a` |
| `tags.csv` | 2,000,072 | `userId`, `movieId`, `tag`, `timestamp` | `963bf4fa4de6b8901868fddd3eb54567` |
| `movies.csv` | 87,585 | `movieId`, `title`, `genres` | `0df90835c19151f9d819d0822e190797` |
| `links.csv` | 87,585 | `movieId`, `imdbId`, `tmdbId` | `8f033867bcb4e6be8792b21468b4fa6e` |

Ratings use half-star increments from 0.5 to 5.0. Timestamps are UTC epoch seconds. The downloader checks all four MD5s after extraction and fails on a mismatch.

### Task and prediction point

Binary classification: `rating >= 4` (positive) versus `rating <= 3.5` (negative). Predict at the rating event, before the rating is observed. The positive rate is 49.8% (15,938,231 of 32,000,204).

Allowed features:

- User history strictly before the current rating: rating count, mean, standard deviation, share at or above 4, days since first rating, days since last rating.
- Movie history strictly before the current rating: rating count, mean, share at or above 4.
- Movie metadata: release year parsed from `title`, genre multi-hot encoding, genre count.
- Event time: year, month, day of week, hour.

Excluded because they are future or identity information:

- Every rating at or after the current rating timestamp. A same-timestamp rating is not used.
- `tags.csv` text. It is user-generated and can leak sentiment or the rating itself; tags are audited but never modeled.
- `links.csv` external identifiers (`imdbId`, `tmdbId`). They are not available at prediction time and add no causal feature.
- Raw `userId` and `movieId` as model features. Use the history aggregates instead; the raw ids are kept only for joins and pairing.

### Cleaning

- Keep ratings from 0.5 to 5.0 in half-star increments. Drop and count anything else.
- Drop ratings whose `movieId` is absent from `movies.csv`; record the count.
- Deduplicate `(userId, movieId)` by keeping the latest timestamp. The local audit finds zero duplicate pairs, so this is a guard against future data changes, not a step that alters the current release.
- Keep `(no genres listed)` as a separate missing-genre indicator; do not impute a genre.
- Keep movies with no ratings in the metadata table; they are candidates for the D2 referential-loss check, not training rows.
- Join ratings to movies on `movieId`. The join is many-to-one and must not change the rating count; verify it.

### Time-varying dimension

Daily user and movie statistics with `effective_from` and `effective_to`:

- `userId`, `as_of_date`, `rating_count`, `mean_rating`, `std_rating`, `share_high`, `days_since_first`, `days_since_last`, `effective_from`, `effective_to`.
- `movieId`, `as_of_date`, `rating_count`, `mean_rating`, `share_high`, `effective_from`, `effective_to`.

A statistic for day `d` uses only ratings with timestamp strictly before `d`. The as-of join picks the version effective at the rating timestamp. The faulty variant joins `is_latest = true`; that is D3.

### Split and sample

- Train: 2019-01-01 to 2021-12-31.
- Validation: 2022-01-01 to 2022-12-31.
- Test: 2023-01-01 to 2023-10-13.
- 1-day embargo between splits.
- Features keep the full history before each split. Ratings before 2019 are used only to build history, never for fitting.
- Sample 500k train, 150k validation, and 150k test rows by a deterministic hash of `(userId, movieId, timestamp)`. Compute the history features on the full table before sampling so that a sampled user keeps the same prior history.
- Record raw rows, usable rows, sampled rows, and dropped rows per split.

### Natural defects to audit

Local audit on the full 32M release:

- 32,000,204 ratings, 200,948 users, 84,432 rated movies, 87,585 movies.
- Zero null ratings, zero ratings outside 0.5-5.0, zero ratings for unknown movies, zero duplicate `(userId, movieId)` pairs, zero duplicate rows, zero future timestamps.
- 7,080 movies have no listed genre; 3,153 movies have no ratings.
- 2,000,072 tags across 51,323 movies; zero null tags, zero orphan tags, zero duplicate rows.
- Timestamps span 1995-01-09T11:46:44 to 2023-10-13T02:29:07 UTC.

The zero natural duplicate rate matters: D5 duplicate ingestion is a treatment with no pre-existing baseline, so the lowest severity is measured against zero, not against an already-dirty table. The missing genres and unrated movies are real joins and feed D2.

### Clean reference result

Not measured yet. The clean baseline is the next deliverable; do not compare defect runs to a placeholder.

## 4. UCI Online Retail II

### Source and files

- Landing page: `https://archive.ics.uci.edu/dataset/502/online+retail+ii`
- Download: `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip` (contains `online_retail_II.xlsx`, 43.5 MB).
- DOI: `10.24432/C5CG6D`.
- License: CC BY 4.0. Redistribution is allowed with attribution, but the repo still downloads by script.

Source columns: `Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`, `Customer ID`, `Country`. The loader renames them to `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country` so the code matches the UCI variable descriptions. The header mismatch is real: the published documentation and the workbook do not use identical names.

1,067,371 line items, 2009-12-01 to 2011-12-09. Missing `CustomerID` is common; missing `Description` is present.

### Task and prediction point

Binary classification: does the customer make another purchase within 90 days of the current invoice? Predict at invoice time, invoice-level aggregation.

Allowed features:

- Recency, frequency, monetary value as of the invoice, computed from prior invoices only.
- Basket size (lines), total quantity, total value, product diversity, average unit price.
- Country, customer tenure (days since first invoice), month, day of week, hour.
- Product price history as of the invoice: median unit price for the same `StockCode` over the prior 30 days.

Excluded because they are future information:

- Any transaction after the invoice timestamp.
- The label window itself.
- Customer identity as a raw feature; use only history-derived aggregates.

### Cleaning

- Drop rows with missing `CustomerID` for the main task. Measure the exact fraction after load; it is a real defect, not a reason to impute.
- Keep `Quantity > 0` and `UnitPrice > 0` for the main task. Cancellations (`InvoiceNo` starting with `C`) and negative quantities are a separate natural-defect audit; do not mix them into the main label without a sensitivity check.
- Aggregate lines to invoices: line count, total quantity, total value, distinct stock codes, dominant country.
- Drop duplicate rows and record the count.

### Time-varying dimension

Product price history as of the invoice:

- `stock_code`, `as_of_date`, `median_unit_price_30d`, `invoice_count_30d`, `effective_from`, `effective_to`.

Computed only from invoices before the current invoice.

### Split and sample

- Train: Dec 2009–Sep 2010, ~20k invoices.
- Validation: Jan–Mar 2011, ~5k invoices.
- Test: Apr–Sep 2011, ~5k invoices.
- 90-day embargo between the end of each feature period and the start of the next, to cover the label window. Train labels run through Dec 2010, validation labels through Jun 2011, and test labels through Dec 2011. The dataset ends 2011-12-09, so drop test invoices after 2011-09-09 or report the right-censoring.

Target ~30k invoices after cleaning; verify.

### Natural defects to audit

Missing `CustomerID` (measured 243,007 of 1,067,371 rows, 22.8%), missing `Description`, negative `Quantity`, zero or negative `UnitPrice`, duplicate rows, cancelled invoices (19,494 rows). Also record the source header mismatch (`Invoice`/`Price`/`Customer ID` vs the documented `InvoiceNo`/`UnitPrice`/`CustomerID`). These are real and inform the injector calibration.

## 5. Licensing and redistribution

| Dataset | License | Raw data in repo | Redistribution | Attribution |
|---|---|---|---|---|
| TLC | NYC Terms of Use | No | Download script only | Cite NYC TLC |
| MovieLens 32M | GroupLens research license | No | Allowed only under the same license terms | Cite Harper & Konstan 2015, DOI 10.1145/2827872 |
| Online Retail II | CC BY 4.0 | No, but allowed | Allowed with attribution | Cite Chen 2012, DOI |

Code: MIT. Documentation: CC BY 4.0. Datasets retain their original licenses. The artifact ships download scripts, checksums, and derived aggregate tables only where the license permits.

## 6. Alternatives considered

| Dataset | Why not selected |
|---|---|
| Olist Brazilian e-commerce | Deferred. It needs Kaggle credentials and repeats the e-commerce task family already covered by Online Retail II. Add it only if a second marketplace domain is explicitly needed. |
| UCI Bike Sharing | Real and CC BY 4.0, but 17,389 hourly rows and no natural join keys. Too small for a pipeline-defect study and redundant with TLC's time-series structure. Keep as a fourth-domain robustness check if reviewers ask. |
| Citi Bike NYC | Real and large, but structurally redundant with TLC and adds another transport domain without a new join topology. |
| Folktables / ACS PUMS | Real and public, but no event timestamps and no natural multi-table joins. Weak fit for streaming and as-of defects. |
| M5 / Instacart / Rossmann | Competition rules restrict redistribution and the prediction tasks are already saturated. |
| MIMIC-IV | Credentialing takes weeks, redistribution is restricted, and reproducibility for reviewers is weaker. |
| IEEE-CIS Fraud | Competition rules and a very saturated task. |
| ACN-Data EV charging | License is ambiguous on the official site. Do not build a paper on unclear terms. |

## 7. Verification log

## 8. Dataset strategy for the first paper

TLC is the primary dataset because it combines a large event-time table, a
time-varying zone dimension, a clear prediction point, and enough rows for
stable repeated experiments. MovieLens and Retail are cross-domain validation,
not prerequisites for the first pilot.

The local execution strategy is:

1. Read one TLC month at a time.
2. Apply the frozen cleaning and timestamp rules before sampling.
3. Cache compact feature tables rather than repeatedly reading raw Parquet.
4. Run one or two conditions at a time on a 16 GB machine.
5. Record raw rows, clean rows, sampled rows, and dropped rows for every run.

The minimum paper can use TLC plus one secondary dataset if time permits. A
third dataset strengthens external validity but does not compensate for weak
defect definitions, missing controls, or poor statistical reporting.

| Date | Check | Result |
|---|---|---|
| 2026-10-28 | TLC 2024 monthly Parquet URLs | Verified on the NYC TLC page |
| 2026-10-28 | TLC zone lookup CSV | Verified on the NYC TLC page |
| 2026-10-28 | TLC 2024 schema and 2025 `cbd_congestion_fee` | Verified on the NYC TLC page |
| 2026-11-07 | MovieLens 32M URL, counts, license, MD5s | Verified on the GroupLens page and README |
| 2026-11-07 | MovieLens local download | 238,950,008 bytes; all four MD5s passed |
| 2026-11-07 | MovieLens local audit | 32,000,204 ratings; 0 invalid; 0 duplicate rows; 7,080 missing genres; 3,153 unrated movies |
| 2026-10-28 | Online Retail II CC BY 4.0, DOI, fields, dates | Verified on the UCI page |
| 2026-10-28 | TLC 2024-01 local audit | 2,964,624 rows; see metrics above |
| 2026-10-28 | TLC 2024 full local audit | 41,169,720 rows; 526,866 invalid durations; out-of-range timestamps detected |
| 2026-10-28 | Online Retail II local audit | 1,067,371 rows; 243,007 missing CustomerID; 67,242 duplicate rows |
| 2026-10-28 | Bike Sharing CC BY 4.0, DOI, size | Verified on the UCI page |

Download scripts must record SHA-256 hashes at first download and re-check them on every run. A hash mismatch is a hard failure, not a warning.
