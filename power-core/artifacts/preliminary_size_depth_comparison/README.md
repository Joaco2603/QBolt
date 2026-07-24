# Comparación preliminar por tamaño y profundidad

Este agregado compara QAOA para 8, 10 y 12 nodos con `p=1,2,3`.
La métrica principal es `E_QAOA / E_optimal`; también se incluyen greedy y GW.

Cada configuración tiene una sola corrida independiente. Por ello no se
reportan desviaciones estándar: se guardan como `null`. Los cinco candidatos
de parámetros no equivalen a cinco corridas independientes.

Los grafos son instancias `proximity-fallback` con pesos de distancia inversa,
no topologías eléctricas confirmadas. No se afirma escalabilidad ni ventaja cuántica.

## Reproducción

```bash
.venv/bin/python power-core/src/benchmarks/aggregate_preliminary.py \
  --input 8=power-core/artifacts/preliminary_local_benchmark_8_escalated/results.json \
  --input 10=power-core/artifacts/preliminary_local_benchmark_10_escalated/results.json \
  --input 12=power-core/artifacts/preliminary_local_benchmark_12_escalated/results.json \
  --output-dir power-core/artifacts/preliminary_size_depth_comparison
```
