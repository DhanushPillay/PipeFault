"""Run the P0 smoke experiment on the TLC fixture."""

from __future__ import annotations

import argparse
import json

from pipefault.config import get_settings
from pipefault.smoke import run_smoke


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--severity", type=float, default=0.10)
    args = parser.parse_args()

    settings = get_settings()
    summary = run_smoke(
        settings.raw_dir,
        settings.artifacts_dir / "smoke",
        seed=args.seed,
        num_boost_round=args.rounds,
        severity=args.severity,
    )
    print(json.dumps(summary["checks"], indent=2))


if __name__ == "__main__":
    main()
