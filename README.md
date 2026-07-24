# Quantathon v2

Reproducible workspace for modelling Costa Rica's transmission network and
evaluating weighted Max-Cut formulations with classical and quantum
optimization components.

The repository currently includes the validated data pipeline, QUBO and Ising
models, QAOA orchestration with local/cloud adapters, greedy and
Goemans-Williamson baselines, an optimizer-independent runner, and reproducible
technical figures.
A complete benchmark CLI and consolidated experiment report are still pending.

## Quick start

Use Python 3.12 or newer and run commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r power-core/requirements.txt

python -m pytest
```

Regenerate the graph inputs and documentation figures:

```bash
python data-analysis/scripts/build_weighted_graph.py
python data-analysis/scripts/build_regional_instance.py
python power-core/src/reports/generate_qubo_walkthrough.py
python power-core/src/reports/generate_ising_walkthrough.py
python power-core/src/reports/generate_qaoa_walkthrough.py
```

Generated JSON and PNG files must be regenerated from their source scripts,
not edited by hand.

## Current capabilities

| Area | Status |
| --- | --- |
| ICE dataset validation and provenance | Implemented |
| Six-node Guanacaste reference instance | Implemented |
| Weighted Max-Cut QUBO and constraints | Implemented |
| Exact QUBO-to-Ising conversion | Implemented and exhaustively tested |
| QAOA orchestration | Implemented with five-or-more seeded BFGS starts |
| Local Guppy/Selene execution adapter | Implemented; optional runtime dependencies required |
| Quantinuum Nexus adapter | Implemented; requires an authenticated compatible session |
| Greedy baseline | Implemented with seeded deterministic tie-breaking |
| Goemans-Williamson baseline | Implemented with seeded hyperplane rounding |
| Optimizer-independent solver runner | Implemented |
| End-to-end benchmark CLI/report | Not yet implemented |

## Visual walkthroughs

- [Weighted Max-Cut QUBO, step by step](power-core/docs/spanish/qubo/README.md)
- [Exact QUBO-to-Ising conversion, step by step](power-core/docs/spanish/ising/README.md)
- [QAOA algorithm, step by step](power-core/docs/spanish/qaoa/README.md)

The Ising walkthrough verifies all 64 assignments of the six-node instance and
shows that `E_Q(x) = E_I(1 - 2x)`, including the constant energy offset.

## Repository structure

```text
.
├── data-analysis/                 # Dataset validation and artifact generators
├── power-core/
│   ├── artifacts/                # Generated graph instances
│   ├── docs/                     # Reproducible English and Spanish reports
│   ├── src/optimizer/            # QUBO, Ising, QAOA and classical solvers
│   ├── src/reports/              # Figure/documentation generators
│   └── tests/                    # Behavioural and reporting tests
└── skills/quantathon-challenge-1/
    └── SKILL.md                  # Challenge constraints and reporting rules
```

## Data model and integrity

The weighted graph currently contains 70 substations, 92 simple undirected
edges, 96 resolved circuits, and 6 unresolved transmission lines. Parallel
circuits are aggregated and source SHA-256 digests are retained.

The graph `weight` is the sum of nominal circuit voltages in kV. It is a
transparent modelling proxy—not capacity, power flow, impedance, failure
probability, or operational risk. The regional artifact's
`synthetic_peak_demand_mw` is a scenario value, not measured local demand.

An inferred geographic fallback exists but is never the default:

```bash
python data-analysis/scripts/build_regional_instance.py \
  --mode proximity-fallback --province Guanacaste --count 6 --neighbors 2
```

Fallback edges represent geographic proximity, not confirmed electrical
topology.

## Reproducibility and reporting

Challenge 1 experiments must preserve seeds, input digests, objective
conventions, optimizer status, failed runs, QAOA depth `p`, and initialization
count. Compare identical instances against Goemans-Williamson, greedy, and an
exact or simulated-annealing reference where feasible. Do not claim quantum
advantage without reproducible evidence.

## Further reading

- [`data-analysis/README.md`](data-analysis/README.md) — source data and generator details.
- [`power-core/README.md`](power-core/README.md) — implementation, environment, and verification guide.
- [`skills/quantathon-challenge-1/SKILL.md`](skills/quantathon-challenge-1/SKILL.md) — mandatory Challenge 1 constraints.
