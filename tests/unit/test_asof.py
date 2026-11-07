from __future__ import annotations

from datetime import date

import polars as pl

from pipefault.features.asof import asof_lookup, build_versions, latest_lookup


def _versions() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "zone": [1, 1, 1, 2, 2],
            "day": [
                date(2024, 1, 1),
                date(2024, 1, 3),
                date(2024, 1, 2),
                date(2024, 1, 1),
                date(2024, 1, 2),
            ],
            "value": [10, 30, 20, 100, 200],
        }
    )


def _facts() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "zone": [1, 1, 1, 2, 2],
            "day": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 4),
                date(2023, 12, 31),
                date(2024, 1, 3),
            ],
            "row": [0, 1, 2, 3, 4],
        }
    )


def test_build_versions_deduplicates_and_sorts() -> None:
    duplicated = pl.concat([_versions(), _versions().head(1)])

    versions = build_versions(duplicated, key="zone", date_column="day", value_columns=["value"])

    assert versions.height == 5
    assert versions["day"].to_list() == [
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 1),
        date(2024, 1, 2),
    ]


def test_asof_lookup_uses_the_effective_version_only() -> None:
    joined = asof_lookup(
        _facts(),
        _versions(),
        key="zone",
        fact_date="day",
        version_date="day",
        value_columns=["value"],
    )

    assert joined["value"].to_list() == [10, 20, 30, None, 200]
    assert joined["row"].to_list() == [0, 1, 2, 3, 4]


def test_asof_lookup_never_leaks_a_future_version() -> None:
    joined = asof_lookup(
        _facts(),
        _versions().rename({"day": "version_day"}),
        key="zone",
        fact_date="day",
        version_date="version_day",
        value_columns=["value"],
    )

    dated = joined.drop_nulls("value")
    assert (dated["version_day"] <= dated["day"]).all()


def test_latest_lookup_returns_the_newest_row_per_key() -> None:
    latest = latest_lookup(_versions(), key="zone", version_date="day", value_columns=["value"])

    assert latest.sort("zone").to_dicts() == [
        {"zone": 1, "value": 30, "day": date(2024, 1, 3)},
        {"zone": 2, "value": 200, "day": date(2024, 1, 2)},
    ]
