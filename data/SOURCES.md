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

## Olist Brazilian e-commerce

- Dataset: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
- License: CC BY-NC-SA 4.0
- Access: free Kaggle account and API credentials.
- Notes: non-commercial and share-alike. Do not redistribute raw files. The
  audit and experiments use the CSVs locally.

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
