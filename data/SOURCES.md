# Data sources

Raw data is downloaded by `pipefault data download` and is never committed.
`data/manifest.sha256` records the SHA-256 of every downloaded file.

## NYC TLC yellow taxi, 2024

- Landing page: <https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>
- Monthly Parquet: `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-MM.parquet`
- Zone lookup: <https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv>
- Data dictionary: <https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf>
- License: NYC Terms of Use, <https://www.nyc.gov/home/terms-of-use.page>
- Notes: 2024 files do not include `cbd_congestion_fee`; that column starts in 2025.

## MovieLens 32M

- Landing page: <https://grouplens.org/datasets/movielens/32m/>
- Download: <https://files.grouplens.org/datasets/movielens/ml-32m.zip>
- README: <https://files.grouplens.org/datasets/movielens/ml-32m-README.html>
- License: GroupLens research license. Research use only; no commercial or
  revenue-bearing use without permission; redistribution only under the same
  terms. Cite Harper & Konstan 2015, <https://doi.org/10.1145/2827872>.
- Files and MD5 checksums:
  - `links.csv`: `8f033867bcb4e6be8792b21468b4fa6e`
  - `movies.csv`: `0df90835c19151f9d819d0822e190797`
  - `ratings.csv`: `cf12b74f9ad4b94a011f079e26d4270a`
  - `tags.csv`: `963bf4fa4de6b8901868fddd3eb54567`
- Notes: 32,000,204 ratings, 2,000,072 tags, 87,585 movies, and 200,948
  users; ratings span 1995-01-09 to 2023-10-12. The downloader verifies every
  MD5 after extraction. Raw files are not committed.

## UCI Online Retail II

- Dataset: <https://archive.ics.uci.edu/dataset/502/online+retail+ii>
- DOI: <https://doi.org/10.24432/C5CG6D>
- License: CC BY 4.0
- Notes: one workbook, two sheets. Missing `CustomerID` and cancellations are
  real defects and are measured, not silently repaired.

## Manifest

`data/manifest.sha256` is generated. Verify it with:

```bash
pipefault data manifest --verify
```
