# Qbolt

Reproducible workspace for Quantathon CR 2026 Challenge 1: modelling Costa
Rica's transmission network and benchmarking weighted Max-Cut with classical
baselines and QAOA.

> **Evidence status:** the ICE-backed six-node study, QUBO/Ising verification,
> greedy, Goemans-Williamson, exhaustive search, preliminary local QAOA, and a
> preliminary multi-size comparison are available. These artifacts are
> exploratory evidence; they are not evidence of quantum advantage, convergence,
> or a Quantinuum H2 run.

## Quick path

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r power-core/requirements.txt
python -m pytest
```

Regenerate the data and walkthrough figures from the repository root:

```bash
python data-analysis/scripts/build_weighted_graph.py
python data-analysis/scripts/build_regional_instance.py
python data-analysis/scripts/plot_regional_graph.py
python power-core/src/reports/generate_qubo_walkthrough.py
python power-core/src/reports/generate_ising_walkthrough.py
python power-core/src/reports/generate_qaoa_walkthrough.py
```

## Documentation map

| Goal | Documentation | Evidence or code |
| --- | --- | --- |
| Read the complete Spanish route | [Project reading guide](power-core/docs/spanish/README.md) | Data, formulation, benchmarks, figures, and limitations in order. |
| Verify source data and assumptions | [Data analysis README](data-analysis/README.md) · [ICE reference (ES)](power-core/docs/spanish/reference-ice-dataset.md) · [ICE reference (EN)](power-core/docs/english/reference-ice-dataset.md) | `data-analysis/dataset/` and generated graph artifacts. |
| Inspect the six-node regional instance | [Regional graph (ES)](power-core/docs/spanish/regional-instance-graph.md) | [`regional_instance.json`](power-core/artifacts/regional_instance.json) · [`regional_instance_graph.png`](power-core/artifacts/regional_instance_graph.png). |
| Follow the QUBO formulation | [QUBO (ES)](power-core/docs/spanish/qubo/README.md) · [English](power-core/docs/english/qubo/README.md) | [`qubo_implementation.py`](power-core/src/optimizer/quantum/qubo/qubo_implementation.py). |
| Verify QUBO → Ising | [Ising (ES)](power-core/docs/spanish/ising/README.md) · [English](power-core/docs/english/ising/README.md) | Exhaustive six-node equivalence tests and [`ising.py`](power-core/src/optimizer/quantum/ising/ising.py). |
| Understand QAOA | [QAOA (ES)](power-core/docs/spanish/qaoa/README.md) · [English](power-core/docs/english/qaoa/README.md) | [`qaoa.py`](power-core/src/optimizer/quantum/qaoa/qaoa.py) and adapters. |
| Review classical baselines | [GW (ES)](power-core/src/optimizer/random_approximation/goemans-williamson.es.md) · [English](power-core/src/optimizer/random_approximation/goemans-williamson.md) | Greedy, GW, and exact reference. |
| Interpret six-node benchmark results | [Benchmark methodology](power-core/docs/spanish/benchmarks/README.md) · [Preliminary results](power-core/artifacts/preliminary_local_benchmark/README.md) | [`results.json`](power-core/artifacts/preliminary_local_benchmark/results.json) and charts. |
| Inspect size/depth comparison | [Size/depth report](power-core/artifacts/preliminary_size_depth_comparison/README.md) | [`aggregate_preliminary.py`](power-core/src/benchmarks/aggregate_preliminary.py), CSV/JSON, and ratio plot. |
| Inspect individual fallback-size runs | [8 nodes](power-core/artifacts/preliminary_local_benchmark_8_escalated/README.md) · [10 nodes](power-core/artifacts/preliminary_local_benchmark_10_escalated/README.md) · [12 nodes](power-core/artifacts/preliminary_local_benchmark_12_escalated/README.md) | Explicitly labelled proximity-fallback instances. |
| Inspect Nexus collection | [Nexus dataset guide](power-core/docs/spanish/benchmarks/nexus-run-dataset.md) | [`nexus_maxcut_runs.json`](power-core/artifacts/nexus_maxcut_runs.json). |
| Check implementation setup | [Power core README](power-core/README.md) | Dependencies, source layout, commands, and limitations. |
| Check delivery constraints | [Challenge skill](skills/quantathon-challenge-1/SKILL.md) | Reproducibility and reporting rules. |

## Experimental evidence

The primary graph has six substations connected through confirmed ICE
transmission lines. Edge weight is summed nominal circuit voltage in kV: a
transparent importance proxy, **not** capacity, power flow, impedance, failure
risk, or a resilience metric.

The size/depth study adds 8-, 10-, and 12-node `proximity-fallback` graphs. Those
edges represent geographic proximity, not confirmed electrical topology. Each
size/depth configuration currently has one independent QAOA run, so the study
shows comparative behavior only; it does not provide uncertainty estimates or
prove scaling.

Nexus integration submits through the Nexus API to a Selene
`StatevectorSimulator`. It is cloud-hosted simulation, not Quantinuum H2
emulation or physical quantum hardware.

## Reproducibility rules

- Regenerate JSON and PNG artifacts from scripts; do not edit them by hand.
- Preserve input digests, seeds, shots, depth `p`, optimizer status, and failures.
- Compare solvers on the identical graph and unchanged weights.
- Report approximation ratio (`cut / OPT`) rather than raw cut alone.
- Do not claim quantum advantage or superiority over Goemans-Williamson.

## Repository layout

```text
.
├── data-analysis/   # ICE validation and graph construction
├── power-core/      # QUBO, Ising, QAOA, classical solvers, reports, tests
│   ├── artifacts/   # Graph and benchmark evidence
│   ├── docs/        # Spanish and English walkthroughs
│   └── src/         # Solvers, benchmarks, experiments, and generators
└── skills/          # Challenge-specific delivery constraints
```

## Documentation directory structure

```text
power-core/docs/
├── english/                          # English documentation
│   ├── reference-ice-dataset.md      # ICE data provenance
│   ├── binary-variables-and-penalties.md
│   ├── synthetic-demand-provenance.md
│   ├── qubo/                          # QUBO formulation and walkthrough figures
│   ├── ising/                         # QUBO-to-Ising conversion and verification
│   └── qaoa/                          # QAOA formulation and execution pipeline
├── spanish/                          # Spanish documentation
│   ├── README.md                      # Reading route and main index
│   ├── reference-ice-dataset.md      # ICE data provenance
│   ├── binary-variables-and-penalties.md
│   ├── demanda-sintetica-procedencia.md
│   ├── regional-instance-graph.md    # Six-node regional instance
│   ├── benchmarks/                    # Benchmark methodology and results
│   │   ├── README.md
│   │   ├── nexus-run-dataset.md
│   │   └── evaluation/                # Evaluation contracts and templates
│   ├── qubo/                          # QUBO formulation and figures
│   ├── ising/                         # QUBO → Ising conversion and verification
│   └── qaoa/                          # QAOA formulation and execution pipeline
└── regional_instance_graph.png        # Shared regional-instance figure
```

Generated results and their explanations are stored in `power-core/artifacts/`;
data-analysis documentation is maintained in `data-analysis/README.md`.
