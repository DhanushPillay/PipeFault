from __future__ import annotations

from datetime import datetime

import polars as pl

from pipefault.data.audit import audit_retail_frame, audit_tlc_frame


def _tlc_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "VendorID": [1, 2, 1],
            "tpep_pickup_datetime": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 1, 10, 5),
                datetime(2024, 1, 1, 11, 0),
            ],
            "tpep_dropoff_datetime": [
                datetime(2024, 1, 1, 10, 20),
                datetime(2024, 1, 1, 10, 5),
                datetime(2024, 1, 1, 14, 1),
            ],
            "passenger_count": [1, None, 0],
            "trip_distance": [1.0, 0.0, 2.0],
            "PULocationID": [1, 300, 2],
            "DOLocationID": [1, 2, 300],
            "fare_amount": [10.0, -1.0, 12.0],
        }
    )


def test_tlc_audit_counts_natural_defects() -> None:
    metrics = audit_tlc_frame(_tlc_frame())

    assert metrics["rows"] == 3
    assert metrics["duplicate_rows"] == 0
    assert metrics["invalid_duration"] == 2
    assert metrics["invalid_distance"] == 1
    assert metrics["negative_fare"] == 1
    assert metrics["invalid_pu_zone"] == 1
    assert metrics["invalid_do_zone"] == 1
    assert metrics["passenger_count_zero"] == 1
    assert metrics["null_counts"]["passenger_count"] == 1


def test_retail_audit_counts_natural_defects() -> None:
    frame = pl.DataFrame(
        {
            "InvoiceNo": ["536365", "C536366", "536367", None],
            "StockCode": ["A", "B", "C", "D"],
            "Description": ["x", None, "z", "w"],
            "Quantity": [1, -1, 2, 3],
            "InvoiceDate": [
                datetime(2010, 12, 1, 8, 0),
                datetime(2010, 12, 2, 9, 0),
                datetime(2010, 12, 3, 10, 0),
                datetime(2010, 12, 4, 11, 0),
            ],
            "UnitPrice": [1.0, 2.0, 0.0, 3.0],
            "CustomerID": [12345.0, None, 67890.0, None],
            "Country": ["United Kingdom", "United Kingdom", "France", "United Kingdom"],
        }
    )

    metrics = audit_retail_frame(frame)

    assert metrics["rows"] == 4
    assert metrics["missing_customer_id"] == 2
    assert metrics["missing_description"] == 1
    assert metrics["negative_quantity"] == 1
    assert metrics["nonpositive_price"] == 1
    assert metrics["cancellations"] == 1
    assert metrics["duplicate_rows"] == 0
