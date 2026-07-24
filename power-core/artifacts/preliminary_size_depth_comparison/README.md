# Comparación preliminar por tamaño y profundidad

Este agregado compara QAOA por tamaño de instancia y profundidad.
La métrica principal es `E_QAOA / E_optimal`; también se incluyen greedy y GW.

Cada configuración tiene una sola corrida independiente. Por ello no se
reportan desviaciones estándar: se guardan como `null`. Los cinco candidatos
de parámetros no equivalen a cinco corridas independientes.

Todas las instancias deben declarar el modelo de aristas y el peso en el JSON.
No se afirma escalabilidad ni ventaja cuántica a partir de una sola corrida.

## Reproducción

```bash
python power-core/src/benchmarks/aggregate_preliminary.py \
  --input 6=power-core/artifacts/preliminary_local_benchmark/results.json \
  --input 8=power-core/artifacts/preliminary_local_benchmark_8/results.json \
  --input 10=power-core/artifacts/preliminary_local_benchmark_10/results.json \
  --input 12=power-core/artifacts/preliminary_local_benchmark_12/results.json \
  --output-dir power-core/artifacts/preliminary_size_depth_comparison
```
