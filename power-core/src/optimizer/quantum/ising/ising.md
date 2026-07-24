# Ising model: QUBO conversion contract

This module provides the deterministic boundary between the project's
minimization QUBO representation and the Ising Hamiltonian consumed by QAOA.
It converts coefficients only; circuit construction, optimization, backend
execution, and result sampling belong to later layers.

> **Status:** implemented and covered by exhaustive QUBO/Ising
> energy-equivalence tests.

## Objective

The `IsingModel` class:

1. build an Ising model from the existing `QuboModel`;
2. preserve every decision and auxiliary variable in deterministic order;
3. expose the constant offset, local fields, and pair couplings;
4. evaluate a complete spin assignment; and
5. preserve QUBO energy exactly under the binary-to-spin mapping.

The conversion must not reinterpret the transmission-network edge weight. In
this project, graph weight remains summed nominal circuit voltage in kV: it is
a modelling proxy, not capacity, power flow, impedance, or operational risk.

## Mathematical convention

The existing QUBO is a minimization objective:

```text
E_Q(x) = c + Σ_i a_i x_i + Σ_(i<j) b_ij x_i x_j
```

where each binary variable is `x_i ∈ {0, 1}`. The Ising spin convention is:

```text
z_i = 1 - 2x_i
x_i = (1 - z_i) / 2
z_i ∈ {-1, +1}
```

Therefore `x = 0` maps to `z = +1`, and `x = 1` maps to `z = -1`.
The resulting minimization Ising energy is:

```text
E_I(z) = C + Σ_i h_i z_i + Σ_(i<j) J_ij z_i z_j
```

with coefficients:

```text
J_ij = b_ij / 4
h_i  = -a_i / 2 - Σ_(j ≠ i) b_ij / 4
C    = c + Σ_i a_i / 2 + Σ_(i<j) b_ij / 4
```

The core invariant is exact energy equivalence:

```text
E_Q(x) = E_I(1 - 2x)
```

The constant `C` MUST be retained. Dropping it would preserve the optimizer's
argmin but would corrupt energy comparisons, benchmark evidence, and later
approximation-ratio calculations.

## Implemented public contract

### `IsingModel.from_qubo`

```text
IsingModel.from_qubo(qubo: QuboModel) -> IsingModel
```

The factory reads the QUBO snapshot without mutating it. The created model
exposes:

| Field | Meaning |
| --- | --- |
| `variables` | Decision variables followed by auxiliary variables, preserving their source order |
| `offset` | Constant `C` in the Ising energy |
| `linear` | Mapping `variable -> h_i`, including every model variable |
| `quadratic` | Canonical mapping `(left, right) -> J_ij` for nonzero couplings |

Pair keys must be canonical and deterministic. Self-couplings are forbidden:
QUBO diagonal terms belong in its linear mapping because `x_i² = x_i`.

### `energy`

```text
energy(spins: Mapping[str, int]) -> float
```

The method evaluates the complete Ising objective, including the offset.
It accepts only assignments that:

- contain every model variable exactly once;
- contain no unknown variable; and
- use integer spin values `-1` or `+1` (booleans are not valid spins).

Invalid assignments raise `ValueError` with the missing variable, unknown
variable, or invalid spin identified in the message.

### Assignment conversion helpers

```text
binary_to_spins(assignment: Mapping[str, int]) -> dict[str, int]
spins_to_binary(assignment: Mapping[str, int]) -> dict[str, int]
```

These helpers implement the documented mapping without changing variable
names or insertion order. They apply the same exact-coverage validation as
`energy`; binary values must be integer `0` or `1`.

## Validation and numerical policy

- The input must be a `QuboModel`; arbitrary mappings are not accepted.
- Every QUBO coefficient and the resulting Ising coefficient must be finite.
- A pair may be supplied in either orientation only after QUBO construction;
  the Ising representation stores one canonical pair.
- Zero-valued couplings may be omitted from `quadratic`; all variables remain
  present in `linear`, even when their local field is zero.
- Conversion is deterministic and performs no rounding or tolerance-based
  coefficient deletion.
- The source `QuboModel` and caller-provided assignments are never mutated.

## Boundaries

This class does not:

- create a Max-Cut QUBO or choose constraint penalties;
- build Pauli operators or a PyTKET circuit;
- execute QAOA or a Quantinuum emulator;
- remove auxiliary variables;
- optimize, normalize, or rescale coefficients; or
- claim that an Ising energy is a physical grid measurement.

Those responsibilities require separate contracts so the algebraic conversion
can be verified exhaustively before quantum execution is introduced.

## Verification

The executable contract lives in
[`../../../../tests/optimizer/quantum/ising/test_ising.py`](../../../../tests/optimizer/quantum/ising/test_ising.py).
The reproducible visual verification is documented in
[`../../../../docs/english/ising/README.md`](../../../../docs/english/ising/README.md).
