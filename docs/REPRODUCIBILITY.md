# Reproducibility

First-class artifact, not an afterthought. Adapted from MARGoS (arXiv:2610.13772) and Liang 2026 (arXiv:2610.02397).

## 1. Required for every run

- Config file (YAML) hashed with SHA-256 and stored with the run.
- Code commit hash (`git rev-parse HEAD`).
- Seed (propagated to every RNG: Python, NumPy, LightGBM).
- Dataset manifest verification (no run starts on a changed download).
- Environment fingerprint (Python version, package versions, OS).
- MLflow run ID and artifact paths.

## 2. Frozen configs

Configs are immutable once a sweep starts. Changing a config creates a new run ID; old runs are never overwritten. Deviations are logged in `docs/PREREGISTRATION.md` with date, reason, and impact on hypotheses.

## 3. Seed propagation

A single seed flows through data sampling (`sample_by_hash`), injection (`rng`), model training, and bootstrap resampling. No hidden global RNG state.

## 4. Data pins

Raw files are SHA-256 pinned in `data/manifest.sha256`. A changed download aborts the run before any feature build.

## 5. Determinism tests

Every injector must pass: same seed gives byte-identical output; exact affected-unit count within tolerance; no in-place mutation of inputs. CI runs these on every push.

## 6. One-command replay

`make reproduce RUN_ID=...` re-executes one run and compares metrics within numerical tolerance. `make experiment` resumes from completed run IDs.
