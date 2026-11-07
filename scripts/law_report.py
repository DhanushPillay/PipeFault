"""Generate the law report from annotated run records."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipefault.analyze.report import conditions_from_records, write_report
from pipefault.runstore import RunStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="artifacts/pilot/runs", help="Run record directory.")
    parser.add_argument("--out", default="artifacts/law", help="Report directory.")
    args = parser.parse_args()

    records = RunStore(Path(args.runs)).list_records()
    conditions = conditions_from_records(records)
    json_path, markdown_path = write_report(Path(args.out), conditions)
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
