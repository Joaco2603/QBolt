# Power Restoration Core

`power-core` contains the implemented optimization boundary for the regional
weighted Max-Cut experiment: QUBO construction, exact Ising conversion, QAOA
orchestration and backends, greedy and Goemans-Williamson baselines, solver
dispatch, and reproducible reports.

The remaining gap is product-level orchestration: there is no consolidated
benchmark CLI that executes every solver and emits the final comparison report.

## Quick path

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r power-core/requirements.txt
python -m pytest
```

Expected result: all `power-core` tests pass.

## Implemented flow

```text
regional_instance.json
        │
        ▼
weighted NetworkX graph
        │
        ▼
QuboModel: E_Q(x) = -weighted_cut(x) + optional penalties
        │
        ▼
IsingModel: E_I(z), with z = 1 - 2x
        │
        ├── QAOA → local Guppy/Selene or authenticated Nexus adapter
        └── classical comparison → greedy or Goemans-Williamson
```

The QUBO-to-Ising conversion preserves the complete energy, including the
constant offset:

```text
E_Q(x) = E_I(1 - 2x)
```

## Components

| Component | Responsibility |
| --- | --- |
| `optimizer.quantum.qubo` | Build weighted Max-Cut QUBOs and optional binary constraints |
| `optimizer.quantum.ising` | Convert `QuboModel` coefficients and evaluate complete spin assignments |
| `optimizer.quantum.qaoa` | Run seeded multi-start parameter optimization and normalize measurements |
| `optimizer.greedy` | Build a deterministic seeded sequential weighted-greedy cut |
| `optimizer.random_approximation` | Solve the Goemans-Williamson SDP and seeded hyperplane rounding |
| `run_solver.py` | Dispatch a validated request without coupling to optimizer mathematics |
| `reports/` | Regenerate QUBO and Ising documentation figures |

QAOA uses at least five deterministic seeded BFGS starts. A returned best
bitstring is the lowest-energy measured sample, not proof of global optimality.
Nexus execution requires a caller-provided authenticated session; credentials
are not stored by this module.

## Reproducible reports

Generate both walkthroughs:

```bash
python power-core/src/reports/generate_qubo_walkthrough.py
python power-core/src/reports/generate_ising_walkthrough.py
python power-core/src/reports/generate_qaoa_walkthrough.py
```

Documentation:

- [QUBO walkthrough in Spanish](docs/spanish/qubo/README.md)
- [QUBO walkthrough in English](docs/english/qubo/README.md)
- [QUBO-to-Ising walkthrough in Spanish](docs/spanish/ising/README.md)
- [QUBO-to-Ising walkthrough in English](docs/english/ising/README.md)
- [QAOA walkthrough in Spanish](docs/spanish/qaoa/README.md)
- [QAOA walkthrough in English](docs/english/qaoa/README.md)
- [Benchmark methodology](docs/spanish/benchmarks/README.md)

Each Ising report includes:

1. the six-step algebraic conversion;
2. QUBO and Ising coefficient visualizations; and
3. exhaustive energy-equivalence evidence for all 64 assignments.

## Project layout

```text
power-core/
├── artifacts/                     # Generated graph JSON files
├── docs/                          # Generated and explanatory documentation
├── requirements.txt               # Pinned direct dependencies
├── src/
│   ├── optimizer/
│   │   ├── quantum/{qubo,ising,qaoa}/
│   │   └── random_approximation/
│   ├── reports/
│   └── run_solver.py
└── tests/
```

## Reproducibility rules

1. Run commands from the repository root.
2. Record every random seed, QAOA depth, shot count, optimizer status, and failed run.
3. Preserve graph source digests and generated artifact provenance.
4. Regenerate files under `artifacts/` and report PNGs; never edit them manually.
5. Benchmark the same instance and unchanged weights across every solver.
6. Do not present simulator output as physical quantum-hardware evidence.

## Known limitations

- There is no unified benchmark command or final cross-solver result table yet.
- Direct dependency versions are pinned, but no transitive lockfile is committed.
- The Nexus adapter cannot guarantee repeatable remote sampling unless the service exposes an independent reproducibility control.
- The voltage-derived graph weight is a modelling proxy, not an electrical capacity or risk metric.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `No module named ...` | Activate `.venv` and reinstall `power-core/requirements.txt`. |
| PyTKET fails under macOS Conda | Use official Python, Homebrew Python, or `pyenv`. |
| Matplotlib cannot write its user cache | Set `MPLCONFIGDIR` to a writable temporary directory. |
| Graph generation reports an `FID mismatch` | Investigate the CSV/GeoJSON data; do not bypass validation. |
