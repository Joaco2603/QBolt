# Power Restoration Core

Reproducible Python workspace for modelling a regional transmission network and
benchmarking power-restoration / Max-Cut solvers. The QUBO, Ising, QAOA,
classical baseline, and Nexus dataset modules are implemented under `src/`.

## Reproduce from a new computer

Use **Python 3.12 or newer**. Python 3.12 is the recommended baseline because
the pinned TKET stack supports it on macOS, Linux, and Windows.

### 1. Install prerequisites

- Git
- Python 3.12+
- Internet access for the first dependency installation

Verify Python before continuing:

```bash
python3 --version
```

The command must report `3.12` or newer. Do not use a Conda Python on macOS for
this project: PyTKET documents installation issues with recent versions in that
environment. Use the official Python installer, Homebrew Python, or `pyenv`.

### 2. Clone the repository

```bash
git clone <REPOSITORY_URL> quantathonv2
cd quantathonv2
```

Replace `<REPOSITORY_URL>` with the repository's real Git URL.

### 3. Create and activate an isolated environment

Run these commands from the repository root.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your terminal should now show `(.venv)`.

### 4. Install the pinned dependencies

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r power-core/requirements.txt
```

`requirements.txt` pins the project's direct dependencies. To reproduce the
exact resolved transitive dependency set on a later machine, export it from the
known-good environment and install that file instead:

```bash
python -m pip freeze --all > requirements.lock
python -m pip install -r requirements.lock
```

Commit `requirements.lock` once a solver implementation and its validated
environment exist. Do not claim byte-for-byte reproducibility from direct pins
alone: transitive dependency releases can change.

### 5. Verify the environment

```bash
python -c "import matplotlib, networkx, numpy, pytket, scipy; print('Environment OK')"
python -m pytest data-analysis/tests
```

Para probar `power-core` desde la raíz del repositorio:

```bash
python -m pytest power-core/tests
```

Expected result: the import command prints `Environment OK`, and the data
analysis test suite passes.

### 6. Regenerate the source graph artifact

```bash
python data-analysis/scripts/build_weighted_graph.py
```

The generator validates the CSV and GeoJSON source pairs by `FID`, records
SHA-256 digests, and writes the graph artifact to:

```text
power-core/artifacts/transmission_weighted_graph.json
```

This path is defined by the existing data generator. It is intentionally not
`power-core/artifacts/`; do not silently move or edit generated artifacts by
hand.

## Project layout

```text
power-core/
├── requirements.txt                 # Pinned direct dependencies
├── README.md                        # This reproducibility guide
├── scripts/                         # Standalone Nexus utilities
├── src/
│   ├── benchmarks/                  # Preliminary reproducible benchmarks
│   ├── experiments/                 # Nexus dataset runner
│   ├── optimizer/                   # Classical and quantum optimizers
│   ├── reports/                     # Reproducible report generators
│   ├── run_solver.py                # Optimizer-independent runner
│   └── x.py                         # Manual Nexus smoke runner
└── tests/                           # Tests for power-core modules
```

## Reproducibility rules

1. Run every command from the repository root.
2. Set and record a random seed for every solver run.
3. Preserve graph source digests and generated JSON provenance.
4. Never edit files under an artifacts directory manually; regenerate them.
5. Benchmark identical instances against QAOA, Goemans-Williamson, greedy, and
   an exact or simulated-annealing reference where feasible.
6. Report QAOA approximation ratio `r = E_QAOA / E_optimal`, including mean,
   standard deviation, optimizer status, initialization count, and depth `p`.

## Current status

The QUBO/Ising transformations, backend-independent QAOA orchestration, local
Selene adapter, Nexus adapter, greedy and Goemans–Williamson baselines, and
versioned Nexus dataset writer are implemented and tested. A complete real-
service benchmark submission still requires credentials, remote runs,
classical result tables, statistical error reporting, and depth-`p` comparison.

## Benchmark plan

The Spanish benchmark plan distinguishes the Challenge 1 mandatory baselines,
the implemented solvers, and useful supplemental experiments:

- [`docs/spanish/benchmarks/README.md`](docs/spanish/benchmarks/README.md)
- [`docs/spanish/benchmarks/nexus-run-dataset.md`](docs/spanish/benchmarks/nexus-run-dataset.md)

Nexus QAOA runs can be collected in the versioned JSON dataset provided by
`src/experiments/nexus_run_dataset.py`. It preserves successful,
non-converged, and failed attempts, input digests, initialization histories,
and result counts. See
[`docs/spanish/benchmarks/nexus-run-dataset.md`](docs/spanish/benchmarks/nexus-run-dataset.md)
for the schema and execution checklist. It does not claim simulator results
as physical Quantinuum hardware results.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `python3 --version` is below 3.12 | Install Python 3.12+ and recreate `.venv`. |
| `No module named ...` | Activate `.venv`, then rerun `python -m pip install -r power-core/requirements.txt`. |
| PyTKET installation fails on macOS Conda | Recreate the environment with an official Python, Homebrew Python, or `pyenv` Python. |
| Graph generation reports an `FID mismatch` | Treat it as a data-integrity failure; inspect the CSV and GeoJSON inputs instead of bypassing validation. |

## Clean reset

Delete only the virtual environment, then repeat steps 3–5:

```bash
rm -rf .venv
```

On Windows PowerShell:

```powershell
Remove-Item -Recurse -Force .venv
```
