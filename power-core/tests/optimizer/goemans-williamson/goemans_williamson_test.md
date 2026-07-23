# Goemans-Williamson Test Contract

## Test target

The executable pytest module is
`power-core/tests/optimizer/goemans-williamson/tests_goemans_williamson.py`.
This Markdown file defines its behavioural contract; `index.py` is not a pytest
test filename and must not be used as the executable test target.

The production API is:

```python
solve_goemans_williamson(
    graph: nx.Graph,
    *,
    seed: int,
    rounds: int = 128,
    solver: str = "SCS",
    optimal_weight: float | None = None,
) -> GoemansWilliamsonResult
```

The immutable result records positive and negative partitions, cut weight, SDP
value, empirical ratio, seed, requested rounds, winning round, solver, and
solver status.

## Strategy adapter contract

`GoemansWilliamsonStrategy` adapts this API to the optimizer-agnostic runner:

- Its stable identifier is `goemans-williamson`.
- It accepts only `rounds` and `solver` in `SolverRunRequest.options`.
- It maps the positive partition to `1` and the negative partition to `0`.
- It recomputes the normalized cut against the request graph.
- It returns validation and SDP failures as `SolverRunResult(status="failed")`.
- It records JSON-serializable SDP and rounding evidence without exposing the
  numerical matrix through shared metadata.

## RED-to-GREEN sequence

1. Validate graph type, string node IDs, simple undirected topology, explicit
   finite non-negative weights, positive rounds, and integer seed.
2. Verify a known cut is summed once per edge and matches the Ising and
   weighted-Laplacian objectives.
3. Verify the SDP on one weighted edge and on a triangle; assert symmetry, unit
   diagonal, PSD feasibility within tolerance, and `cut <= optimum <= sdp`.
4. Verify invalid or failed solver outputs are rejected, while only
   tolerance-sized PSD errors are repaired before factorization.
5. Verify fixed-seed reproducibility, exhaustive disjoint partitions,
   deterministic zero-dot-product handling, and earliest-round tie-breaking.
6. Verify that selecting the best of multiple hyperplanes is never worse than
   the first hyperplane from the same seeded generator sequence.
7. Enumerate every assignment for small graphs to validate exact optima and
   empirical ratios. Do not assert the 0.87856 expectation for an individual
   seeded run.
8. Cover empty graphs, isolated nodes, disconnected graphs, and zero weights;
   require `empirical_ratio is None` when the exact optimum is zero.
9. Load `power-core/artifacts/regional_instance.json` deterministically, verify
   that brute force yields the reference optimum `1058.0 kV`, and compare
   partitions only up to complement.
10. Verify the strategy defaults, option validation, normalized partition,
    recomputed cut, immutable request forwarding, and structured failures.
11. Inject the strategy into `SolverRunner` and verify the regional reference
    instance without adding optimizer-specific branches to the runner.

## Acceptance commands

```bash
python -m pytest power-core/tests/optimizer/goemans-williamson/tests_goemans_williamson.py
python -m pytest power-core/tests/optimizer/test_goemans_williamson_strategy.py
python -m pytest power-core/tests/test_run_solver.py
python -m pytest power-core/tests
```
