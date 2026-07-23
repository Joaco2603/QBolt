# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains the `data-analysis/` Python module for producing reproducible transmission-network artifacts.

- `data-analysis/dataset/` holds the authoritative input pairs: `Subestaciones.{csv,geojson}` and `LineasDeTransmision.{csv,geojson}`.
- `data-analysis/scripts/` contains standalone generators such as `build_weighted_graph.py` and `build_regional_instance.py`.
- `data-analysis/tests/` contains pytest tests. Tests load scripts directly, so keep script entry points import-safe.
- Generated JSON belongs under `power-core/artifacts/`; do not edit generated artifacts by hand.

## Build, Test, and Development Commands

Run commands from the repository root:

```bash
# Build the validated graph artifact
python data-analysis/scripts/build_weighted_graph.py

# Produce a fallback regional instance
python data-analysis/scripts/build_regional_instance.py --province Guanacaste --count 6 --neighbors 2

# Run the data-analysis test suite
python -m pytest data-analysis/tests
```

The graph builder cross-checks CSV and GeoJSON records by `FID` and records source digests. Treat validation failures as data issues to investigate, not errors to bypass.

## Coding Style & Naming Conventions

Use Python 3 with four-space indentation, type hints for public helpers, and concise docstrings. Prefer `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for module constants, and descriptive `Path`-based filesystem handling. Keep transformations deterministic and preserve provenance in generated data. Use standard-library modules unless a dependency is clearly justified.

## Testing Guidelines

Add or update pytest tests in `data-analysis/tests/` for every behavior change. Name files `test_*.py` and tests `test_<expected_behavior>()`. Cover both successful transformations and validation/error paths. For changes to matching, aggregation, or output schemas, assert stable counts and representative records rather than only checking that output exists.

## Commit & Pull Request Guidelines

Git history is not available in this checkout, so no repository-specific convention can be verified. Use conventional commits, for example `feat(data-analysis): add endpoint alias`. Keep commits focused. Pull requests should explain the data or behavior change, list validation run, identify regenerated artifacts, and call out any changed assumptions or limitations. Include a small output sample when the generated JSON schema changes.

## Data Integrity

Do not silently modify source datasets or reinterpret graph weights. The current `weight` is the summed nominal circuit voltage (kV), not capacity, power flow, impedance, or risk. Document any new proxy and its limitations in the generator output and README.

## Project Skills

- `skills/quantathon-challenge-1/SKILL.md` — use for Challenge 1 QAOA/Max-Cut work; it enforces reproducibility, benchmarking, reporting, and honest-limitations requirements.
