# Quantathon v2

Reproducible workspace for modelling Costa Rica's transmission network and preparing small weighted graph instances for power-restoration and Max-Cut/QAOA experiments.

The repository currently delivers **validated grid data and generated JSON artifacts**. The quantum and classical solver entry points under `power-core/src/` are scaffolds, so benchmark results are not yet produced by this checkout.

## Quick start

Use Python 3.12 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\Activate.ps1
python -m pip install -r power-core/requirements.txt
python -m pytest data-analysis/tests
```

Regenerate the full weighted graph and the documented six-node regional instance:

```bash
python data-analysis/scripts/build_weighted_graph.py
python data-analysis/scripts/build_regional_instance.py
```

Expected outputs:

- `power-core/artifacts/transmission_weighted_graph.json`: 70 substations, 92 simple undirected edges, 96 resolved circuits, and 6 unresolved lines.
- `power-core/artifacts/regional_instance.json`: a six-node Guanacaste instance using confirmed transmission connectivity.

Run commands from the repository root. Generated artifacts must be regenerated, not edited by hand.

## Repository structure

```text
.
├── data-analysis/
│   ├── dataset/                 # Authoritative CSV and GeoJSON source pairs
│   ├── scripts/                 # Deterministic graph and instance builders
│   ├── tests/                   # pytest validation and transformation tests
│   └── README.md                # Data-analysis details
├── power-core/
│   ├── artifacts/               # Generated graph JSON files
│   ├── requirements.txt         # Pinned direct Python dependencies
│   ├── src/                     # Solver and benchmark entry-point scaffolds
│   └── README.md                # Environment and reproducibility notes
└── skills/quantathon-challenge-1/
    └── SKILL.md                 # Challenge 1 reporting and reproducibility rules
```

## Data pipeline

1. `build_weighted_graph.py` loads the four source files.
2. CSV and GeoJSON records are cross-checked by `FID`, including shared attributes and CRS.
3. Transmission circuit endpoints are normalized for accents, known numeric suffixes, and the `Garita`/`La Garita` alias.
4. Parallel circuits are aggregated into one undirected edge.
5. Source SHA-256 digests and unresolved lines are preserved in the generated artifact.
6. `build_regional_instance.py` extracts the confirmed six-node scenario from that graph.

The graph `weight` is the sum of nominal circuit voltages in kV. It is a transparent importance proxy—not capacity, power flow, impedance, or failure risk. The regional artifact's `synthetic_peak_demand_mw` is an equal-share scenario value, not observed local demand.

## Explicit proximity fallback

The regional builder supports an inferred geographic fallback, but it is not the default and must be identified in any report:

```bash
python data-analysis/scripts/build_regional_instance.py \
  --mode proximity-fallback --province Guanacaste --count 6 --neighbors 2
```

These edges represent inverse geographic distance, not confirmed electrical topology.

## Reproducibility and reporting

For Challenge 1 work, document seeds, source digests, QUBO conventions, and failed runs. Compare QAOA with Goemans–Williamson, greedy, and an exact or simulated-annealing reference where feasible. Report approximation ratio, initialization count, optimizer status, and depth `p`; do not claim quantum advantage without evidence.

## Current limitations

- `power-core/src/` does not yet contain implemented solver or benchmark logic.
- Direct dependency pins are provided, but no transitive lockfile is committed.
- Unresolved transmission lines are retained for auditability but excluded from graph edges.
- Synthetic demand values must not be presented as measured substation demand.

## Further reading

- [`data-analysis/README.md`](data-analysis/README.md) — source data and generator details.
- [`power-core/README.md`](power-core/README.md) — environment setup and reproducibility guidance.
- [`skills/quantathon-challenge-1/SKILL.md`](skills/quantathon-challenge-1/SKILL.md) — mandatory Challenge 1 constraints.
