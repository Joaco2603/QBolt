# Dataset de corridas Nexus

`src/experiments/nexus_run_dataset.py` conserva corridas QAOA del simulador
Selene/Nexus en un JSON versionado. No es un artefacto del grafo y no debe
editarse a mano.

## Esquema y estados

El documento tiene `schema_version`, `dataset_type`, `objective`,
`comparison_specification`, una instantánea de `instance` y la lista `runs`.
La instancia conserva nodos, aristas ponderadas, procedencia y
`digest_sha256`. El digest cubre IDs, extremos, pesos y procedencia; cambiar
cualquiera de ellos produce otro digest y bloquea la mezcla de corridas.

Cada corrida conserva `run_id`, fecha UTC, digest, entorno/versiones,
`solver` y `result`. `solver` registra `layers_p`, `shots`, `seed`, número de
inicios, `optimizer_method`, `selected_start` y el historial de inicios.
`result.status` es uno de:

- `succeeded`: el optimizador seleccionado convergió;
- `not_converged`: hubo resultado y mediciones, pero el optimizador no reportó
  convergencia;
- `failed`: Nexus, autenticación, cuota, compilación o ejecución falló.

Los fallos se guardan con tipo y mensaje, sin inventar conteos. Las corridas
no convergentes también se conservan. El resultado exitoso registra conteos,
probabilidades, energías por bitstring, partición, corte, `OPT` y
`approximation_ratio = cut_value / optimal_cut` cuando `OPT` está disponible.
El código acepta resultados normalizados por `QAOA`; los adaptadores soportan
las formas `QsysResult` (`collated_counts()`) y `BackendResult`
(`get_counts()`).

## Acumulación y bloqueo

El comando abre el JSON existente y agrega una corrida; no lo reemplaza.
Rechaza `run_id` duplicados y `load_or_create` rechaza un digest de instancia
distinto. Un archivo hermano `.lock` se bloquea durante la lectura-modificación-
escritura para serializar escritores concurrentes. El JSON se escribe primero
en un temporal y luego se reemplaza atómicamente.

## Ejecución

Desde la raíz del repositorio, usando el entorno reproducible:

```bash
.venv/bin/python power-core/src/experiments/nexus_run_dataset.py \
  --run-id regional-v2-p1-seed7 \
  --seed 7 --layers 1 --starts 5 --shots 1024 \
  --optimal-cut 1058.0
```

La corrida requiere credenciales Nexus, cuota de simulación y las versiones
fijadas en `power-core/requirements.txt`. El CLI autentica, crea/selecciona el
proyecto, comprueba la cuota, construye el QUBO mediante
`optimizer.quantum.qubo.build_max_cut_qubo`, ejecuta QAOA y persiste éxito o
fallo. Un fallo se vuelve a lanzar después de guardarse para que no pase
desapercibido.

La semilla de cada inicio se envía al backend como
`StatevectorSimulator(seed=...)`. La reproducibilidad exacta de conteos sigue
dependiendo de que el servicio remoto respete ese parámetro y de mantener la
misma configuración y versión del servicio.

## Matriz de versiones compatible

| Componente | Versión fijada |
| --- | --- |
| Python | 3.12+ (verificado en 3.14) |
| `qnexus` | 0.45.0 |
| `guppylang` | 0.21.16 |
| `selene-sim` | 0.2.17 |
| `pytket` | 2.18.1 |
| `numpy` | 2.5.1 |
| `scipy` | 1.18.0 |

No se soportan checkouts que requieran la ruta histórica
`optimizer.quantum.qubo_implementation`.

## Checklist de ejecución y envío

1. Confirmar Python y reinstalar `power-core/requirements.txt` en `.venv`.
2. Verificar el grafo y su procedencia; calcular `OPT` por búsqueda exhaustiva
   para instancias de Challenge 1 cuando sea factible.
3. Ejecutar al menos cinco inicializaciones por configuración y conservar
   semillas, `p`, shots, estado y todos los fallos.
4. Comparar la misma instancia con greedy, Goemans–Williamson y una referencia
   exacta o simulated annealing.
5. Revisar el digest, los ratios, medias y desviaciones estándar antes de
   enviar resultados.
6. Describir Selene/Nexus como emulación; una ejecución remota no es evidencia
   de hardware físico ni de ventaja cuántica.

Una corrida real aún requiere validación manual del servicio remoto. El dataset
por sí solo no convierte el proyecto en una entrega completa del Challenge:
también hacen falta corridas reales, baselines clásicos, ratios, errores
estadísticos y comparación por profundidad `p`.
