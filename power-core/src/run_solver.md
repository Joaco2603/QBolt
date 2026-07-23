# Solver runner: optimizer-agnostic strategy contract

`run_solver.py` will be the application boundary for executing a Max-Cut
optimization. It must depend on a strategy contract, never on a concrete
optimizer. Adding QAOA, Goemans-Williamson, greedy, exact, or a future solver
must therefore require an adapter and registration, not a change to the runner
workflow.

> **Status:** design and TDD contract only. No production implementation or
> optimizer completion is part of this document.

## Decision

Use the Strategy pattern with explicit request and result value objects:

```text
CLI / caller
    -> SolverRunRequest
    -> SolverRunner
    -> SolverStrategy selected by identifier
    -> SolverRunResult
```

The runner owns orchestration and validation. Each strategy owns only the
translation from the common request into its optimizer-specific execution.

| Responsibility | Owner |
| --- | --- |
| Load or receive the weighted graph | caller / runner boundary |
| Validate common run inputs | runner |
| Select a named optimizer | registry or injected strategy mapping |
| Translate shared inputs into optimizer-specific settings | strategy adapter |
| Execute the optimizer | strategy adapter |
| Normalize output and preserve provenance | strategy adapter, validated by runner |
| Compare solvers or render reports | benchmark/report modules, not this runner |

## Public contract to implement later

### `SolverRunRequest`

An immutable request must contain only information that every strategy can
understand:

| Field | Meaning | Rule |
| --- | --- | --- |
| `graph` | Weighted undirected Max-Cut graph | required; edge weights remain the dataset's nominal kV proxy |
| `optimizer_id` | Stable strategy key, e.g. `qaoa` | required; must resolve exactly once |
| `seed` | Reproducibility seed | required; forwarded unchanged when supported |
| `options` | Optimizer-specific configuration | mapping; runner treats it as opaque |
| `run_id` | Caller-supplied trace identifier | optional; never generated from nondeterministic state |

The runner must not add optimizer-specific parameters such as QAOA depth,
shots, or Goemans-Williamson rounding trials to this shared request. Those
belong in `options` and are interpreted exclusively by the selected strategy.

### `SolverStrategy`

Every adapter must expose one stable identifier and one execution operation:

```text
id: str
solve(request: SolverRunRequest) -> SolverRunResult
```

The strategy may reject invalid entries in `request.options`, but it must not
mutate the graph or the request. It must either return a normalized result or
raise a documented domain error; it must not return partial, untyped data.

### `SolverRunResult`

All strategies must return the same result shape:

| Field | Meaning |
| --- | --- |
| `optimizer_id` | Identifier of the strategy that actually ran |
| `status` | `succeeded`, `failed`, or `not_converged` |
| `partition` | Mapping of every graph node to one of the two cut partitions |
| `cut_value` | Weighted Max-Cut value under the project convention |
| `seed` | Seed used for this run |
| `metadata` | JSON-serializable strategy evidence: parameters, iterations, timings, backend, and diagnostics |
| `error` | Structured failure information when status is not `succeeded` |

`cut_value` must always be evaluated against the input graph by the same
project convention. A strategy may report an internal objective, but that value
must be retained in `metadata` and never replace the normalized cut value.

## Selection and extensibility

The runner receives a registry (or mapping) of `optimizer_id` to
`SolverStrategy`. This makes supported optimizers explicit and makes tests able
to inject a fake strategy without importing quantum or numerical dependencies.

To add a future optimizer:

1. Implement the `SolverStrategy` contract in its own optimizer module.
2. Define and validate only its own `options` schema.
3. Register the adapter under a unique, stable identifier.
4. Add the shared contract tests plus adapter-specific tests.
5. Do not modify `SolverRunner` unless the shared contract itself changes.

Duplicate identifiers are a configuration error. An unknown identifier is a
user-facing validation error that lists the registered identifiers in stable
order. There is no implicit default optimizer: callers must choose one.

## Runner workflow

1. Validate the graph and common request fields before selecting the strategy.
2. Resolve `optimizer_id` from the injected registry.
3. Invoke exactly one strategy once with the original request.
4. Validate that the returned result names the selected strategy, covers every
   graph node exactly once, and has a finite normalized `cut_value` when it
   succeeds.
5. Return the validated result unchanged in meaning; do not swallow failures or
   substitute another optimizer.

This boundary deliberately does **not** implement fallback behavior. Silent
fallback makes a benchmark dishonest: the reported optimizer would not be the
one that produced the result. A future explicit fallback policy may be composed
outside the runner and must record every attempted strategy.

## Invariants and failure policy

- The runner must not import or branch on concrete optimizer classes.
- The request graph, seed, and optimizer identifier are immutable for the run.
- `partition` must contain each input node once and only values representing the
  two Max-Cut sides.
- A failed or non-converged run remains observable through `status`, `error`,
  and `metadata`; it is never relabeled as successful.
- Randomized strategies must record the actual seed and enough configuration in
  `metadata` to reproduce the attempt.
- The runner does not compare approximation ratios. That belongs to the
  benchmark layer, which can use the normalized `cut_value` from every result.

## Out of scope

- Implementing QAOA, Goemans-Williamson, greedy, exact, or any other optimizer.
- Defining optimizer-specific option schemas.
- CLI argument parsing, persistence, report rendering, and cross-optimizer
  benchmarking.
- Retrying, fallback, or automatic optimizer selection.

## TDD handoff

Implement the tests described in
[`../tests/run_solver_test.md`](../tests/run_solver_test.md) first. Production
code begins only after the initial contract tests are RED.
