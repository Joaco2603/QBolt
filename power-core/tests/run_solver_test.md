# `run_solver` TDD test contract

These tests define the behavior of the future optimizer-agnostic solver runner.
They are documentation only: do not implement `run_solver.py` or any optimizer
while this contract is being reviewed.

## Test seam

Tests must inject a registry containing small fake `SolverStrategy` adapters.
The fakes record the request they receive and return deterministic,
preconstructed results. They must not import QAOA, PyTKET, SciPy, or a concrete
project optimizer.

Use a minimal weighted graph fixture with at least one edge and a fixed seed.
This isolates the runner contract from optimizer mathematics.

## RED → GREEN test order

Implement one test at a time in this order. First make the test fail because
the public contract does not exist; then add only enough production behavior to
make it pass; then refactor with all prior tests green.

| Order | Test | Expected behavior |
| ---: | --- | --- |
| 1 | `test_runner_delegates_to_the_strategy_selected_by_optimizer_id` | A request for a registered identifier invokes that strategy exactly once and returns its normalized result. |
| 2 | `test_runner_forwards_the_original_request_without_mutation` | The selected strategy receives the same graph, seed, identifier, options, and run ID supplied by the caller. |
| 3 | `test_runner_selects_different_registered_strategies_without_conditional_logic` | Two identifiers reach two different fakes; the runner does not require a branch per optimizer. |
| 4 | `test_runner_rejects_an_unknown_optimizer_id_with_registered_identifiers` | An unresolved identifier raises a domain validation error before any strategy executes. |
| 5 | `test_runner_rejects_duplicate_strategy_identifiers` | Registry construction/configuration fails deterministically for duplicate IDs. |
| 6 | `test_runner_requires_an_explicit_optimizer_id` | Missing or blank selection fails; no default strategy is chosen. |
| 7 | `test_runner_rejects_a_success_result_with_missing_partition_nodes` | A successful result that omits an input node is rejected. |
| 8 | `test_runner_rejects_a_success_result_with_unknown_partition_nodes` | A successful result containing a node absent from the input graph is rejected. |
| 9 | `test_runner_rejects_a_success_result_with_an_invalid_partition_label` | A successful result may use only the two allowed partition labels. |
| 10 | `test_runner_rejects_a_success_result_with_non_finite_cut_value` | `NaN` and infinities cannot cross the application boundary as successful results. |
| 11 | `test_runner_preserves_failed_and_not_converged_results` | The runner returns these statuses with their error and metadata; it does not convert them to success or raise them away. |
| 12 | `test_runner_does_not_fallback_after_a_strategy_failure` | A failure from the chosen strategy is visible and no second registered strategy is called. |

## Shared fixtures

| Fixture | Purpose |
| --- | --- |
| `weighted_graph` | Deterministic, small undirected graph with known node IDs and weights. |
| `request` | Valid `SolverRunRequest` with explicit optimizer ID, seed, immutable options, and optional run ID. |
| `recording_strategy` | Fake adapter that records calls and returns a valid successful result. |
| `failing_strategy` | Fake adapter that returns a structured `failed` result. |
| `not_converged_strategy` | Fake adapter that returns a structured `not_converged` result. |
| `registry` | Injected mapping/registry; never a global mutable singleton. |

## Assertions that matter

- Assert call counts, selected identifier, and request identity/value—not only
  the final cut value.
- Assert graph-node coverage exactly, including rejection of both missing and
  extra nodes.
- Assert the seed and `options` reach the selected strategy unchanged.
- Assert error messages expose the invalid optimizer ID and the stable list of
  available IDs, without exposing implementation class names.
- Assert no optimizer fallback by checking that an unselected fake has zero
  calls.
- Keep optimizer-specific behavior out of this file; QAOA depth, shots,
  backend selection, and Goemans-Williamson rounding belong in each adapter's
  own test module.

## Deliberately excluded tests

The following are not runner responsibilities and must not be added here:

- Correctness or performance of a concrete optimizer.
- QAOA circuit construction, initialization, or convergence.
- Goemans-Williamson SDP/rounding behavior.
- Approximation-ratio calculation or multi-optimizer ranking.
- File loading, CLI parsing, report generation, retries, or fallback policy.

## Completion gate

The runner is ready for implementation only when these tests exist and fail for
the expected missing-contract reason. It is ready to leave the TDD cycle only
when every test passes and the implementation has no direct imports of concrete
optimizer adapters.
