# QAOA execution backends

`backends.py` implements the execution adapters used by the backend-independent
[`QAOA`](qaoa.md) orchestrator. An adapter receives a fully specified
`QAOAProgram` plus one value of `gamma` and `beta` per layer, executes the
corresponding circuit, and returns measured bitstring counts in a
`MeasurementBatch`.

The module provides two adapters:

| Adapter | `name` | Execution target | Requirements |
| --- | --- | --- | --- |
| `LocalGuppySeleneBackend` | `guppy-selene` | Local Selene state-vector emulator | `guppylang` and `selene-sim` |
| `NexusBackend` | `quantinuum-nexus` | A pre-authenticated Nexus session | Compatible authenticated Nexus API/session |

Neither adapter optimizes QAOA parameters or evaluates Ising energies. Those
operations remain in `QAOA`; adapters are responsible only for compiling and
executing one bound circuit and translating its measurements.

## Backend contract

Both classes implement the `QAOABackend` protocol:

```python
def execute(
    program: QAOAProgram,
    gamma: Sequence[float],
    beta: Sequence[float],
    *,
    shots: int,
    seed: int | None,
) -> MeasurementBatch: ...
```

`QAOAProgram` carries the canonical variable order, linear and quadratic Ising
terms, constant offset, and number of layers. The offset is intentionally not
encoded in a quantum gate because it contributes only a global phase; `QAOA`
adds it back when it evaluates energies.

### Bitstring convention

A program variable at index `i` is allocated to qubit `q{i}`. Measurement
results are returned in precisely that order:

```text
variables = ("north", "south", "west")
bitstring = "010"  ->  q0=0, q1=1, q2=0
```

The QAOA core validates the final mapping: bitstrings must contain only `0` and
`1`, must have exactly one bit per variable, and counts must be non-negative
integers with at least one measured shot.

## Circuit generation

`_build_guppy_program()` creates a Guppy function for one concrete parameter
assignment. It rejects `gamma` or `beta` sequences whose length differs from
`program.layers`.

For every circuit it:

1. Allocates one qubit per program variable and applies `H` to prepare `|+⟩`.
2. Repeats one cost/mixer block for each layer.
3. Applies `RZ` to each linear coefficient.
4. Implements each quadratic `Z_i Z_j` term as `CX(i, j) → RZ(j) → CX(i, j)`.
5. Applies `RX` to every qubit for the mixer.
6. Measures every qubit and records it under `q0`, `q1`, etc.

Guppy angles are generated in half turns: a radian value `θ` is emitted as
`angle(θ / π)`. The circuit source is compiled dynamically because all QAOA
parameters are bound for an individual objective evaluation.

## Local execution

Use `LocalGuppySeleneBackend` for a local state-vector simulation:

```python
from optimizer.quantum import IsingModel, LocalGuppySeleneBackend, QAOA

result = QAOA(layers=1, starts=5, seed=7).run_local(
    model,
    backend=LocalGuppySeleneBackend(),
    shots=1024,
)
```

The adapter builds the Guppy program and executes:

```text
main.emulator(n_qubits=...).statevector_sim().with_seed(seed).with_shots(shots).run()
```

It then iterates over `result.results`, reads the named measurements, and
aggregates them into `{bitstring: count}`. If Guppy or Selene is unavailable,
the adapter raises `RuntimeError` chained from the original `ImportError`.

## Nexus execution

`NexusBackend` submits the compiled Guppy/HUGR package through an
already-authenticated session. It never logs in, requests credentials, or
persists secrets.

```python
import qnexus as qnx
from optimizer.quantum import NexusBackend, QAOA

backend = NexusBackend(qnx)
result = QAOA(layers=1, starts=5, seed=7).run_cloud(
    model,
    session=qnx,
    backend=backend,
    shots=1024,
)
```

The session object must expose the APIs used by the adapter:

- `hugr.upload(...)` to upload `main.compile()`;
- `models.SeleneConfig` and `models.StatevectorSimulator` to construct the
  backend configuration;
- `start_execute_job(...)` to submit the program;
- `jobs.wait_for(...)`, `jobs.results(...)`, and the downloaded result's
  `collated_counts()` to collect measurements.

The job is configured with the program's qubit count and `shots` requested by
the caller. Missing session APIs produce a `RuntimeError` that explains the
expected Nexus capabilities.

> **Reproducibility note:** the concrete Nexus submission path does not pass
> the `seed` argument to the remote simulator. Therefore, although `QAOA`
> supplies deterministic evaluation seeds to every adapter call, exact sampled
> counts from this backend depend on the Nexus execution service unless the
> session/service supplies reproducibility controls independently.

### Nexus count normalization

Nexus collated-count keys can be strings or backend-specific tuple wrappers.
`_counts_from_collated_counts()` extracts a bitstring where possible, combines
duplicate entries, and uses `_canonical_counts()` to validate and sort the
result according to the program's variable count. An unsupported key shape is
converted to text and subsequently rejected if it is not a valid bitstring.

## Test and custom executors

Both constructors accept an optional `executor` callable. When supplied, it
bypasses Guppy/Selene or Nexus work and is called with the same program,
parameters, shot count, and seed expected by the adapter:

```python
def local_executor(program, gamma, beta, *, shots, seed):
    return {"00": shots}

backend = LocalGuppySeleneBackend(executor=local_executor)
```

For `NexusBackend`, the session is the first positional argument:

```python
def nexus_executor(session, program, gamma, beta, *, shots, seed):
    return {"00": shots}

backend = NexusBackend(authenticated_session, executor=nexus_executor)
```

A custom executor may return either a `MeasurementBatch` or a mapping from
bitstrings to integer counts. Mappings are wrapped in `MeasurementBatch`; they
still undergo validation in the QAOA core. This injection point is useful for
unit tests and for integrating another compatible execution service without
changing the optimizer.

## Errors and limitations

- `NexusBackend(None)` raises `ValueError`; a session is required even when a
  custom executor is used.
- An invalid number of `gamma` or `beta` values raises `ValueError` during
  circuit generation.
- The local adapter requires optional external packages; the cloud adapter
  requires an authenticated, API-compatible Nexus session.
- State-vector emulation samples a simulator; neither adapter by itself
  provides a result from quantum hardware or evidence of quantum advantage.
