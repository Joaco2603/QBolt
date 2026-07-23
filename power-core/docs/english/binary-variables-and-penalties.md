# Binary variables and constraint penalties (conceptual guide)

This section documents the modelling step that precedes an optimization
implementation. It does **not** construct a QUBO matrix, run a solver, or add
solver code.

### 1. Define one binary decision per choice

Use a binary variable when a decision has exactly two states:

\[
x_i \in \{0, 1\}
\]

Interpret `0` and `1` in domain language before writing any formula. For
example, `x_i = 1` may mean that line, facility, or node `i` is selected, while
`x_i = 0` means it is not selected. Keep this meaning consistent throughout the
model.

| Decision | Binary variable | Meaning of `1` |
| --- | --- | --- |
| Select a transmission line | `x_line` | The line belongs to the selected set. |
| Place a node on side A of a partition | `x_node` | The node is assigned to side A; `0` assigns it to side B. |
| Activate a restoration action | `x_action` | The action is included in the plan. |

A binary variable is not a quantity. If the decision can take several integer
levels, use an integer formulation or encode those levels explicitly; do not
pretend that one bit represents more information than it does.

### 2. Turn a hard constraint into a non-negative violation

For a constraint to be enforced through a penalty, first write an expression
that is zero exactly when the constraint is satisfied and positive otherwise.
Then add that expression to a minimization objective with a positive penalty
weight `P`:

\[
\text{penalized objective} = \text{base objective} + P \cdot \text{violation}
\]

The penalty weight must be large enough that breaking the constraint is never
preferred merely to improve the base objective. An oversized weight can also
make numerical optimization poorly conditioned, so choose and justify it from
known objective bounds rather than guessing.

### Common simple constraints

| Constraint | Satisfied when | Penalty term | Notes |
| --- | --- | --- | --- |
| Select exactly one option | `Σᵢ xᵢ = 1` | `P(Σᵢ xᵢ - 1)²` | Zero only for one selected option. |
| Select at most one option | `Σᵢ xᵢ ≤ 1` | `P Σᵢ<ⱼ xᵢxⱼ` | Each simultaneously selected pair incurs a cost. |
| Select at least one option | `Σᵢ xᵢ ≥ 1` | `P(1 - Σᵢ xᵢ)²` **only when** `Σᵢ xᵢ ∈ {0,1}` | For more than two candidates, use an auxiliary-variable construction or another suitable encoding; this square would also penalize selecting more than one. |
| Require `x_a` only if `x_b` | `x_a ≤ x_b` | `P x_a(1 - x_b)` | The only violation is `x_a = 1`, `x_b = 0`. |
| Prevent two choices together | `x_a + x_b ≤ 1` | `P x_ax_b` | Appropriate for mutually exclusive choices. |
| Force two choices to agree | `x_a = x_b` | `P(x_a - x_b)²` | Penalizes the two mismatched assignments. |

Here `Σ` denotes a sum over the indicated binary variables. Because binary
variables satisfy `x_i² = x_i`, squared expressions can later be simplified
algebraically. That simplification is deliberately not performed in this
README and no QUBO is produced here.

### 3. Validate the penalty before implementation

For a small constraint, enumerate every binary assignment on paper or in a
table. Confirm that valid assignments have zero penalty and invalid assignments
have a strictly positive penalty.

For example, for `x_a ≤ x_b`, the term `x_a(1 - x_b)` gives:

| `x_a` | `x_b` | Valid? | Penalty |
| ---: | ---: | --- | ---: |
| 0 | 0 | Yes | 0 |
| 0 | 1 | Yes | 0 |
| 1 | 0 | No | 1 |
| 1 | 1 | Yes | 0 |

This truth-table check catches sign errors and reversed implications before
any optimizer or quantum workflow is involved.

### Scope boundary

This guide stops at defining variables and documenting penalty expressions.
Constructing a QUBO, selecting penalty magnitudes for a concrete instance, and
executing classical or quantum solvers remain future, separately validated
work.
