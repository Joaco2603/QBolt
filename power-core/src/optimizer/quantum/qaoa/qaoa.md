# Backend-agnostic QAOA

`optimizer.quantum.QAOA` minimizes an [`IsingModel`](../ising/ising.md) with

```text
E(z) = offset + sum(h_i z_i) + sum(J_ij z_i z_j),  z_i in {-1, +1}
```

The model's variable order is the qubit and bitstring order. Each circuit
starts in `|+>` and applies `p` cost/mixer layers with bound `gamma` and
`beta` parameters. The constant offset is not a gate, but is included in all
reported energies.

## Execution

The shared optimizer accepts a backend adapter. Local execution uses Guppy and
Selene's state-vector emulator:

```python
from optimizer.quantum import IsingModel, LocalGuppySeleneBackend, QAOA

result = QAOA(layers=1, starts=5, seed=7).run_local(
    model,
    backend=LocalGuppySeleneBackend(),
    shots=1024,
)
```

Cloud execution receives an already-authenticated Nexus module/session. This
module never performs login or stores credentials:

```python
import qnexus as qnx
from optimizer.quantum import NexusBackend, QAOA

result = QAOA(layers=1, starts=5, seed=7, max_parallel_starts=2).run_cloud(
    model,
    session=qnx,
    backend=NexusBackend(qnx),
    shots=1024,
)
```

`QAOAResult` contains the best observed bitstring, its spin assignment and
energy, optimized parameters, counts, probabilities, per-bitstring energies,
backend name, depth, shot count, the selected BFGS outcome status, objective
evaluation count, and backend metadata. “Best” means the lowest-energy measured
sample; it is not a proof of global optimality.

The default optimizer uses five deterministic seeded BFGS starts. The current
The default optimizer uses five deterministic seeded BFGS starts. Each start's
seed, evaluation count, objective value, optimizer status, and error (if any)
are preserved in `QAOAResult.metadata["starts"]`; the selected start remains
the one exposed by the top-level optimizer fields. A benchmark report must
preserve every start separately rather than treating one selected result as
complete failed-run evidence.

## Visual walkthrough

- [English](../../../../docs/english/qaoa/README.md)
- [Spanish](../../../../docs/spanish/qaoa/README.md)
