# Qbolt⚡
_By BitQBit for Dojo Coding's QUANTATHON CR 2026_

> **Quantathon v2 — Reproducible Quantum & Classical Optimization Benchmark**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-171%20passed-2ea44f.svg?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Quantum Integration](https://img.shields.io/badge/Quantum-Quantinuum%20Nexus-6f42c1.svg?style=for-the-badge)](https://www.quantinuum.com/)
[![Event](https://img.shields.io/badge/Quantathon-v2-orange.svg?style=for-the-badge)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](#)

---

## Executive Summary

**Qbolt** is a fully reproducible workspace designed for modeling Costa Rica's transmission network and evaluating weighted **Max-Cut** formulations. It features classical baselines alongside quantum optimization pipelines (QUBO, Ising, and QAOA) with support for both local simulators and cloud hardware.

> **Key Highlights for Judges:**
> * **Data Provenance:** Built upon validated real-world transmission network topology datasets (ICE).
> * **Mathematical Rigor:** Exact QUBO-to-Ising mapping verified exhaustively across all $2^N$ state assignments.
> * **Testing & Rigor:** $171$ unit & integration tests passing with zero mock dependencies on mathematical verification.
> * **Hardware Readiness:** Dual backend architecture supporting both local execution and **Quantinuum Nexus**.

---

## Capabilities Matrix

| Area | Feature / Module | Status |
| :--- | :--- | :---: |
| **Data Pipeline** | ICE dataset validation and provenance tracking | 🟢 **Implemented** |
| **Topology** | 6-node Guanacaste reference regional instance | 🟢 **Implemented** |
| **Formulations** | Weighted Max-Cut QUBO with constraint penalization | 🟢 **Implemented** |
| **Ising Conversion** | Exact QUBO-to-Ising conversion & energy offset tracking | 🟢 **Implemented** |
| **Algorithms** | QAOA orchestration ($5+$ seeded BFGS multi-start) | 🟢 **Implemented** |
| **Adapters** | Local Guppy/Selene execution engine | 🟢 **Implemented** |
| **Adapters** | Quantinuum Nexus cloud integration | 🟢 **Implemented** |
| **Baselines** | Greedy solver with deterministic tie-breaking | 🟢 **Implemented** |
| **Baselines** | Goemans-Williamson algorithm (SDP + hyperplane rounding) | 🟢 **Implemented** |
| **Execution** | Optimizer-independent unified solver runner | 🟢 **Implemented** |
| **Reporting** | End-to-end benchmark CLI and consolidated report | 🟡 **In Progress** |

---

## Quick Start

### 1. Environment Setup

Requirement: **Python 3.12+**

```bash
# Clone and prepare virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1

# Install core dependencies
python -m pip install -r power-core/requirements.txt

# Run full test suite
python -m pytest

```

### 2. Generate Graph Artifacts & Visualizations

Execute the following pipeline to build graph instances and render step-by-step documentation figures:

```bash
python data-analysis/scripts/build_weighted_graph.py
python data-analysis/scripts/build_regional_instance.py
python power-core/src/reports/generate_qubo_walkthrough.py
python power-core/src/reports/generate_ising_walkthrough.py
python power-core/src/reports/generate_qaoa_walkthrough.py

```

> ⚠️ **Note:** All output JSON and PNG files are deterministic target artifacts and must be generated via scripts rather than modified manually.

---

## Experimental Validation & Results

We conducted experimental QAOA / Iceberg QED validation on the dedicated `feat/iceberg-qed-qaoa` branch:

* **Compilation Target:** 6-node Guanacaste regional Max-Cut instance (6 logical / 8 physical data qubits).
* **Optimization Analysis:** Comparative schedule mapping (naive vs. co-compiled).
* **Test Verification:** `171 passed` end-to-end.

> ℹ️ **Scientific Disclaimer:** This benchmark reports structural circuit metrics and compiler pass performance. It does not assert hardware fidelity on Quantinuum H2-1, noisy post-selection superiority, or physical quantum advantage. The experimental branch remains cleanly isolated from `main`.

---

## Visual Walkthroughs

Explore step-by-step mathematical derivations and walkthroughs:

* 📐 **[Weighted Max-Cut QUBO Walkthrough](./power-core/docs/english/qubo/README.md)**
* 🔄 **[Exact QUBO-to-Ising Conversion](./power-core/docs/english/ising/README.md)**
* ⚛️ **[QAOA Execution Pipeline](./power-core/docs/english/qaoa/README.md)**

The Ising verification module systematically checks all 64 state assignments ($2^6$) of the Guanacaste instance, proving exact equivalence:

$$E_Q(x) = E_I(1 - 2x)$$

including the constant energy offset.

---

## Repository Structure

```text
.
├── data-analysis/             # Dataset validation and artifact generators
├── power-core/
│   ├── artifacts/             # Generated graph instances & exported models
│   ├── docs/                  # Reproducible documentation (EN / ES)
│   ├── src/
│   │   ├── optimizer/         # QUBO, Ising, QAOA & classical solvers
│   │   └── reports/           # Technical visualization generators
│   └── tests/                 # Unit, behavioral, and reporting tests
└── skills/
    └── quantathon-challenge-1/ # Challenge criteria & evaluation rules

```

---

## Data Model & Provenance

The primary electrical graph consists of:

* **70** substations
* **92** simple undirected edges
* **96** resolved electrical circuits
* **6** unresolved transmission lines

Parallel circuits are aggregated and validated using **SHA-256 source data digests**.

> **Modeling Notes:**
> * Edge **weight** corresponds to the sum of nominal circuit voltages in kV (used as a transparent topological proxy).
> * `synthetic_peak_demand_mw` represents a scenario test parameter rather than real-time telemetry.

### Fallback Mode

To evaluate fallback heuristics without confirmed topology:

```bash
python data-analysis/scripts/build_regional_instance.py --mode proximity-fallback --province Guanacaste --count 6 --neighbors 2
```

---

## ⚖️ Reproducibility Protocol

All experiments under **Challenge 1** maintain strict scientific rigor:

1. Fixed random seeds and hashed input parameters.
2. Logged objective functions, optimizer convergence status, and QAOA depth $p$.
3. Direct benchmarking against Goemans-Williamson, greedy heuristics, and exact references.
4. Transparency regarding failed runs and parameter tuning limits.

---

## 📚 Further Reading

* 📑 [`data-analysis/README.md`](./data-analysis/README.md) — Source data origin, scripts, and integrity specs.
* 🛠️ [`power-core/README.md`](./power-core/README.md) — Environment setup, solver architecture, and verification.
* 📜 [`skills/quantathon-challenge-1/SKILL.md`](./skills/quantathon-challenge-1/SKILL.md) — Official Challenge 1 rules and evaluation metrics.