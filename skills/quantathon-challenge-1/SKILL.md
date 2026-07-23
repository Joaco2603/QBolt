---
name: quantathon-challenge-1
description: "Trigger: Quantathon Challenge 1, QAOA, Max-Cut, fault-zone partitioning. Enforce challenge constraints and reproducible reporting."
license: Apache-2.0
metadata:
  author: Joaquin Alberto Pappa Larreal
  version: "1.0"
---

## Activation Contract

Use for any Challenge 1 work: grid-graph preparation, QUBO/Max-Cut formulation, QAOA, classical benchmarks, experiments, reports, slides, or submission checks.

## Hard Rules

- Model a weighted regional grid with 6–12 nodes; preserve node, edge, weight, and source provenance.
- Define the Max-Cut objective and QUBO convention explicitly. Verify the QUBO on a small instance before QAOA.
- Use Pytket and/or Guppy for quantum execution; target Quantinuum H2 emulation and never claim unsupported hardware results.
- Report the approximation ratio `r = E_QAOA / E_optimal`, not only raw cut cost. Keep maximization/minimization conventions consistent.
- Benchmark the same instance against Goemans–Williamson and greedy; include brute force or simulated annealing where feasible.
- Run at least five distinct QAOA initializations per configuration and report mean, standard deviation, optimizer status, and parameter depth `p`.
- Show `r` versus `p` and compare at two or more instance sizes when making scaling claims.
- Never claim quantum advantage or superiority over Goemans–Williamson. State limitations, noise effects, and extrapolation boundaries honestly.

## Decision Gates

| Situation | Required action |
|---|---|
| Real ICE/Costa Rican data is used | Cite the source and explain the SDG 7, 9, and 13 causal impact. |
| QEC or mitigation is added | Compare encoded/mitigated and baseline results; report the depth-performance tradeoff. |
| Optimizer does not converge | Record the failure; try BFGS or a grid-search warm start without hiding failed runs. |

## Execution Steps

1. Provide `requirements.txt`, a README, graph data, and one script or notebook that regenerates every reported figure and number from a clean environment.
2. Produce the QUBO verification, QAOA results, classical baseline table, and approximation-ratio plot.
3. Prepare a technical report of at most eight pages with error bars and an honest limitations section.
4. Include a 200-word-or-less SDK statement and ensure presentation claims match reproducible evidence.

## Output Contract

Return reproducible commands, sources, seeds, complete result tables, and failed-run handling. Flag every missing mandatory deliverable before declaring the work submission-ready.

## References

- `../../data-analysis/README.md` — current graph data provenance and weighting limitations.
