# `IsingModel` TDD test contract

These tests will define the behavior of the future QUBO-to-Ising conversion.
They are documentation only: do not create `ising.py` while this contract is
under review.

## Test seam

Tests will load the existing `QuboModel` and the future `IsingModel` directly
from their source modules. They will use small hand-built QUBOs so expected
coefficients can be calculated by inspection, without importing QAOA, PyTKET,
SciPy, a backend, or transmission-network datasets.

Use exact binary enumeration for models with at most three variables. For every
binary assignment `x`, derive `z = 1 - 2x` and assert:

```text
qubo.minimum_energy(x) == ising.energy(z)
```

For QUBOs with auxiliary variables, minimize the Ising energy over every
auxiliary-spin assignment and compare that minimum with
`qubo.minimum_energy(primary_assignment)`. Do not compare a primary-only QUBO
assignment directly with one arbitrarily chosen complete Ising assignment.

## RED → GREEN test order

Implement one test at a time. Each new test must fail for the intended missing
behavior before adding the smallest production change that makes it pass.

| Order | Test | Expected behavior |
| ---: | --- | --- |
| 1 | `test_from_qubo_converts_one_linear_term` | For `E_Q = c + ax`, the model produces `C = c + a/2` and `h = -a/2`. |
| 2 | `test_from_qubo_converts_one_quadratic_term` | For `bxy`, it produces `J_xy = b/4`, subtracts `b/4` from both local fields, and adds `b/4` to the offset. |
| 3 | `test_from_qubo_accumulates_multiple_terms_per_variable` | A variable's local field includes its linear coefficient and every incident quadratic coefficient. |
| 4 | `test_from_qubo_preserves_decision_then_auxiliary_variable_order` | `variables` is deterministic and retains all QUBO variables. |
| 5 | `test_from_qubo_canonicalizes_pair_keys` | Each pair appears once in stable orientation and no self-coupling is emitted. |
| 6 | `test_energy_matches_qubo_for_every_two_variable_assignment` | Exhaustive assignments have exactly equal QUBO and Ising energies. |
| 7 | `test_energy_matches_qubo_for_a_three_variable_constraint_model` | Exact equivalence also holds for a representative `ConstraintBuilder` output. |
| 8 | `test_energy_includes_the_constant_offset` | A constant-only contribution remains observable in every assignment. |
| 9 | `test_binary_to_spins_uses_zero_to_positive_one_and_one_to_negative_one` | The documented mapping is applied without changing names or order. |
| 10 | `test_spins_to_binary_is_the_inverse_mapping` | A round trip reproduces the original valid binary assignment. |
| 11 | `test_energy_rejects_missing_and_unknown_variables` | Assignment coverage must match the model exactly. |
| 12 | `test_energy_rejects_non_spin_values_including_booleans` | Only integer `-1` and `+1` values are accepted. |
| 13 | `test_binary_to_spins_rejects_non_binary_values_including_booleans` | Only integer `0` and `1` values are accepted. |
| 14 | `test_from_qubo_rejects_non_finite_coefficients` | `NaN` and infinities cannot enter or leave the conversion boundary. |
| 15 | `test_conversion_does_not_mutate_the_qubo` | Source variables and coefficient mappings remain unchanged. |
| 16 | `test_energy_does_not_mutate_the_spin_assignment` | Evaluation is a read-only operation. |

## Initial fixtures

| Fixture | Purpose |
| --- | --- |
| `linear_qubo` | One variable with a nonzero offset and linear coefficient |
| `pair_qubo` | Two variables with linear terms and one quadratic interaction |
| `three_variable_qubo` | Small representative model for exhaustive enumeration |
| `qubo_with_auxiliary` | Confirms decision/auxiliary ordering and full variable preservation |
| `all_binary_assignments` | Deterministic enumeration of `0/1` assignments |

Use coefficients that make incorrect signs and a missing constant obvious.
Include at least one negative linear coefficient and one positive quadratic
coefficient. Avoid relying only on symmetric examples where a sign error could
accidentally pass.

## Assertions that matter

- Assert `offset`, every local field, and every pair coupling separately before
  relying on energy equivalence.
- Assert the convention `x = 0 -> z = +1` and `x = 1 -> z = -1` explicitly.
- Assert exact variable coverage for both decision and auxiliary variables.
- Assert all assignments for the small model, not one convenient optimum.
- Assert input snapshots before and after conversion/evaluation to prove there
  is no mutation.
- Use `pytest.approx` only for floating-point arithmetic effects; it must not
  hide a wrong algebraic convention.

## Deliberately excluded tests

The following belong to other modules and must not be added here:

- construction of a Max-Cut objective from a graph;
- selection or calibration of QUBO penalty values;
- Pauli-operator or quantum-circuit construction;
- QAOA depth, shots, optimizer convergence, or backend execution;
- decoding sampled bitstrings into a graph partition;
- approximation-ratio calculation and comparison with classical solvers.

## Completion gates

The documentation phase is complete when the mathematical convention, public
API, validation policy, and RED test order are accepted.

The future implementation phase starts by creating only the first executable
test. It is complete only after all documented tests pass, exhaustive energy
equivalence is demonstrated, and the production module contains no quantum
backend dependency.
