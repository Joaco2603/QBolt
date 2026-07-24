# Power Restoration Core

`power-core` contains the optimization and reporting boundary for the weighted
regional Max-Cut experiment: QUBO construction, exact Ising conversion, QAOA
orchestration/backends, greedy and Goemans-Williamson baselines, experiment
collection, size/depth aggregation, and reproducible walkthroughs.

## Quick path

From the repository root, with Python 3.12 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r power-core/requirements.txt
python -m pytest power-core/tests
```

## Implemented flow

```text
regional_instance.json
        ↓
weighted NetworkX graph
        ↓
QuboModel: minimize E_Q(x) = -weighted_cut(x)
        ↓
IsingModel: E_Q(x) = E_I(1 - 2x)
        ├── QAOA → local Guppy/Selene or Nexus-hosted Selene simulation
        └── classical → exact search, greedy, Goemans-Williamson
```

## Documentation and evidence

| Topic | Link |
| --- | --- |
| Documentation reading route | [Spanish guide](docs/spanish/README.md) |
| QUBO walkthrough | [Spanish](docs/spanish/qubo/README.md) · [English](docs/english/qubo/README.md) |
| Ising walkthrough | [Spanish](docs/spanish/ising/README.md) · [English](docs/english/ising/README.md) |
| QAOA walkthrough | [Spanish](docs/spanish/qaoa/README.md) · [English](docs/english/qaoa/README.md) |
| Benchmark protocol | [Spanish benchmark guide](docs/spanish/benchmarks/README.md) |
| Six-node evidence | [Artifact README](artifacts/preliminary_local_benchmark/README.md) |
| Size/depth evidence | [Aggregate report](artifacts/preliminary_size_depth_comparison/README.md) |
| Nexus collection | [Dataset guide](docs/spanish/benchmarks/nexus-run-dataset.md) |
| ICE provenance | [Spanish](docs/spanish/reference-ice-dataset.md) · [English](docs/english/reference-ice-dataset.md) |

## Reproduce the preliminary benchmarks

```bash
python power-core/src/benchmarks/reproduce_local.py
```

This single entry point rebuilds the confirmed ICE instances for 6, 8, 10, and
12 nodes, executes exact, greedy, GW, and local Guppy/Selene QAOA on each one,
then regenerates the aggregate JSON, CSV, READMEs, and figures.

These are preliminary local Guppy/Selene runs with one independent run per
size/depth configuration. Five parameter candidates are not five independent
experiments; no error bars or convergence claim is made.

## Nexus execution boundary

`NexusBackend` uses Nexus with Selene `StatevectorSimulator`. Describe those
runs as simulation; they are neither Quantinuum H2 emulation nor physical
hardware evidence. Use the [Nexus dataset collector](src/experiments/nexus_run_dataset.py)
to preserve configuration, counts, optimizer details, and failures.

## Known limitations

- The final multi-run study with five or more independent runs per configuration
  and uncertainty reporting is not complete.
- The 6/8/10/12-node family uses confirmed ICE topology, but its deterministic
  connected expansion is a benchmark-selection rule, not an operational zoning
  study or proof of asymptotic scaling.
- Direct dependency pins are committed, but no transitive lockfile is committed.
- Nominal-voltage weights are a modelling proxy, not electrical capacity or risk.

## Project layout

```text
power-core/
├── artifacts/      # Generated graph and benchmark evidence
├── docs/           # Spanish and English walkthroughs
├── scripts/        # Nexus inspection utilities
├── src/
│   ├── benchmarks/ # Local benchmarks and aggregators
│   ├── experiments/# Nexus dataset collection
│   ├── optimizer/  # QUBO, Ising, QAOA, greedy, GW
│   └── reports/    # Walkthrough figure generators
└── tests/          # Behavioural and reporting tests
```
