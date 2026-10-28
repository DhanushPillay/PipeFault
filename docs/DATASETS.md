# Datasets

Three real public datasets. No synthetic rows, no semi-synthetic control, no generated customers or trips. The only constructed element is the defect treatment applied to real records; the clean run is the reference. This is standard fault injection, not fabricated data.

## 1. Summary

| Dataset | Role | Source | License | Size | Dates | Task | Target |
|---|---|---|---|---|---|---|---|
| NYC TLC yellow taxi, 2024 | Primary; large, event-time, static + time-varying dimension | NYC TLC / AWS Open Data | NYC Terms of Use | 12 monthly files; 800k sample | Jan–Dec 2024 | Pre-trip ETA regression | Trip duration (min) |
| Olist Brazilian e-commerce | Multi-table joins; classification | Kaggle `olistbr/brazilian-ecommerce` | CC BY-NC-SA 4.0 | 99,441 orders; 112,650 items; 99,224 reviews | Sep 2016–Aug 2018 | Review score classification | `review_score >= 4` |
| UCI Online Retail II | Single-table retail; long horizon; repeat-purchase label | UCI ML Repository, DOI 10.24432/C5CG6D | CC BY 4.0 | 1,067,371 lines | Dec 2009–Dec 2011 | Repeat purchase within 90 days | Binary |

All three are downloadable without a subscription. Olist requires a free Kaggle account and acceptance of the dataset license.

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

## 3. Olist Brazilian e-commerce

### Source and files

- Kaggle: `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`
- Download: `kaggle datasets download -d olistbr/brazilian-ecommerce` after accepting the license.
- License: CC BY-NC-SA 4.0. Non-commercial, share-alike. Do not redistribute raw files. Academic research is permitted; check the license text before any commercial use.

Nine CSV files. Row counts below are from the public dataset listing; they will be replaced by the local audit once Kaggle access is configured.

| File | Listed rows | Join key |
|---|---|---|
| `olist_orders_dataset.csv` | 99,441 | `order_id`, `customer_id` |
| `olist_order_items_dataset.csv` | 112,650 | `order_id`, `product_id`, `seller_id` |
| `olist_order_payments_dataset.csv` | 103,886 | `order_id` |
| `olist_order_reviews_dataset.csv` | 99,224 | `order_id`, `review_id` |
| `olist_customers_dataset.csv` | 99,441 | `customer_id`, `customer_unique_id` |
| `olist_products_dataset.csv` | 32,951 | `product_id` |
| `olist_sellers_dataset.csv` | 3,095 | `seller_id` |
| `olist_geolocation_dataset.csv` | 1,000,163 | zip prefix |
| `product_category_name_translation.csv` | 71 | category name |

### Task and prediction point

Binary classification: `review_score >= 4` (positive) versus `<= 3` (negative). Predict at order approval, before delivery.

Allowed features:

- Purchase and approval timestamps: hour, day of week, month, approval latency.
- `order_estimated_delivery_date` minus purchase timestamp.
- Item count, total price, total freight, freight-to-price ratio, product category, product weight and dimensions.
- Customer state, seller state, whether customer and seller are in the same state.
- Payment type, installments, payment value.
- Seller history as of the order date: cumulative orders, average review score, cancellation rate.

Excluded because they are post-outcome or label-derived:

- `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_status` after approval.
- `review_creation_date`, `review_answer_timestamp`, `review_comment_title`, `review_comment_message`.
- Any aggregate computed with reviews created after the order date.

The review text is not used at all. Only the numeric score is the label.

### Cleaning

- Keep all orders with a non-null `review_score`. Do not condition on final delivery status; selecting only delivered orders would condition on a post-approval outcome. Record the status distribution and report it as a limitation.
- Sensitivity check: repeat the main result on delivered-only orders. If the conclusion changes, report both and do not hide the selection effect.
- Drop orders with no items or no payment record; record the count.
- Aggregate order items to one row per order: item count, total price, total freight, product diversity, dominant category.
- Aggregate payments to one row per order: payment type (mode), installments (max), payment value (sum).
- Deduplicate reviews by `order_id`; if multiple reviews exist, keep the latest by `review_creation_date` and record the count.
- Do not impute missing product dimensions with the global mean; use a missing indicator and a median by category fit on train only.

### Time-varying dimension

Seller history as of the order date:

- `seller_id`, `as_of_date`, `cum_orders`, `avg_review_score`, `cancel_rate`, `effective_from`, `effective_to`.

Computed only from orders before the current order's purchase timestamp. The as-of join prevents future reviews from leaking into the feature.

### Split and sample

- Train: Sep 2016–Dec 2017, ~70k orders.
- Validation: Jan–May 2018, ~10k orders.
- Test: Jun–Aug 2018, ~8k orders.
- 7-day embargo between splits.
- Target ~90k orders after filtering; verify after cleaning.

### Natural defects to audit

Orders without items, items without orders, reviews without orders, missing delivery timestamps, duplicate reviews, zero or negative freight, missing product category, missing dimensions. Record counts before injection.

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
| Olist | CC BY-NC-SA 4.0 | No | Not permitted without share-alike compliance | Cite Olist / Kaggle |
| Online Retail II | CC BY 4.0 | No, but allowed | Allowed with attribution | Cite Chen 2012, DOI |

Code: MIT. Documentation: CC BY 4.0. Datasets retain their original licenses. The artifact ships download scripts, checksums, and derived aggregate tables only where the license permits.

## 6. Alternatives considered

| Dataset | Why not selected |
|---|---|
| UCI Bike Sharing | Real and CC BY 4.0, but 17,389 hourly rows and no natural join keys. Too small for a pipeline-defect study and redundant with TLC's time-series structure. Keep as a fourth-domain robustness check if reviewers ask. |
| Citi Bike NYC | Real and large, but structurally redundant with TLC and adds another transport domain without a new join topology. |
| Folktables / ACS PUMS | Real and public, but no event timestamps and no natural multi-table joins. Weak fit for streaming and as-of defects. |
| M5 / Instacart / Rossmann | Competition rules restrict redistribution and the prediction tasks are already saturated. |
| MIMIC-IV | Credentialing takes weeks, redistribution is restricted, and reproducibility for reviewers is weaker. |
| IEEE-CIS Fraud | Competition rules and a very saturated task. |
| ACN-Data EV charging | License is ambiguous on the official site. Do not build a paper on unclear terms. |

## 7. Verification log

| Date | Check | Result |
|---|---|---|
| 2026-10-28 | TLC 2024 monthly Parquet URLs | Verified on the NYC TLC page |
| 2026-10-28 | TLC zone lookup CSV | Verified on the NYC TLC page |
| 2026-10-28 | TLC 2024 schema and 2025 `cbd_congestion_fee` | Verified on the NYC TLC page |
| 2026-10-28 | Olist row counts and table names | Listed on Kaggle; local load pending credentials |
| 2026-10-28 | Olist license CC BY-NC-SA 4.0 | Kaggle dataset listing |
| 2026-10-28 | Online Retail II CC BY 4.0, DOI, fields, dates | Verified on the UCI page |
| 2026-10-28 | TLC 2024-01 local audit | 2,964,624 rows; see metrics above |
| 2026-10-28 | TLC 2024 full local audit | 41,169,720 rows; 526,866 invalid durations; out-of-range timestamps detected |
| 2026-10-28 | Online Retail II local audit | 1,067,371 rows; 243,007 missing CustomerID; 67,242 duplicate rows |
| 2026-10-28 | Bike Sharing CC BY 4.0, DOI, size | Verified on the UCI page |

Download scripts must record SHA-256 hashes at first download and re-check them on every run. A hash mismatch is a hard failure, not a warning.
