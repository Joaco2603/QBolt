# Dataset de corridas de Nexus

`src/experiments/nexus_run_dataset.py` guarda las corridas de QAOA ejecutadas
por el simulador de Nexus en un JSON versionado. El registro incluye el digest
del grafo, configuración, semilla, `p`, shots, conteos, bitstring, partición,
valor del corte, `OPT`, ratio, estado del optimizador y errores.

El grafo usado para registrar debe ser exactamente el mismo que se usó para
crear la instancia. El recolector recalcula el digest y rechaza mezclas de
instancias.

El comando abre el JSON existente y agrega la nueva corrida; no reemplaza las
corridas previas. Rechaza `run_id` duplicados y bloquea temporalmente el archivo
de salida para serializar ejecuciones concurrentes sobre el mismo dataset.

Ejemplo de integración alrededor de `QAOA.run_cloud`:

```python
from pathlib import Path

from experiments.nexus_run_dataset import NexusRunDataset, build_instance_snapshot

instance = build_instance_snapshot(
    graph,
    instance_id="regional-confirmed-v2",
    optimal_cut=1058.0,
)
dataset = NexusRunDataset(
    instance=instance,
    path=Path("power-core/artifacts/nexus_maxcut_runs.json"),
)

try:
    result = QAOA(layers=1, starts=5, seed=7).run_cloud(
        ising, session=qnx, backend=nexus_backend, shots=1024
    )
except Exception as error:
    dataset.append_failure(
        run_id="regional-confirmed-v2-p1-seed7",
        seed=7, layers=1, starts=5, shots=1024, error=error,
    )
else:
    dataset.append_result(
        result,
        graph=graph,
        seed=7,
        layers=1,
        starts=5,
        shots=1024,
        run_id="regional-confirmed-v2-p1-seed7",
        optimal_cut=1058.0,
    )
dataset.save()
```

El archivo resultante se puede comparar por `instance_digest_sha256`,
`solver.layers_p`, `solver.seed`, `solver.backend` y `result.approximation_ratio`.
Los resultados de Selene/Nexus se describen como emulación; el dataset no
interpreta una ejecución en simulador como hardware físico.

También puede ejecutarse directamente desde la raíz del repositorio:

```bash
.venv/bin/python power-core/src/experiments/nexus_run_dataset.py \
  --run-id regional-v2-p1-seed7 \
  --seed 7 \
  --layers 1 \
  --starts 5 \
  --shots 1024 \
  --optimal-cut 1058.0
```

Requiere las dependencias de `power-core/requirements.txt`, credenciales de
Nexus y cuota de simulación. Si Nexus falla, la corrida fallida se guarda y el
comando termina con error para que el fallo no pase desapercibido.
