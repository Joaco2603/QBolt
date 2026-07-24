# Guía de lectura del proyecto

Esta es la ruta recomendada para entender el experimento sin saltar entre
archivos. El resultado central es una comparación reproducible de cortes
ponderados sobre una instancia regional de seis subestaciones. **La evidencia
actual es preliminar**: sirve para leer el pipeline, no para afirmar ventaja
cuántica ni convergencia de QAOA.

## Ruta rápida

1. **Qué datos usamos** — [procedencia del dataset](reference-ice-dataset.md).
2. **Qué grafo entra al experimento** — [instancia regional](regional-instance-graph.md)
   y `power-core/artifacts/regional_instance.json`.
3. **Qué se optimiza** — [QUBO](qubo/README.md) y luego
   [QUBO → Ising](ising/README.md).
4. **Cómo funciona el método cuántico** — [QAOA](qaoa/README.md).
5. **Contra qué se compara** — [plan de benchmarks](benchmarks/README.md).
6. **Qué significan los números** — la evidencia preliminar en
   `power-core/artifacts/preliminary_local_benchmark/`. El directorio
   `benchmarks/evaluation/` todavía contiene únicamente la convención y el
   template para una futura evaluación versionada.

## Contexto mínimo

| Concepto | Lectura correcta |
| --- | --- |
| Grafo | Nodos = subestaciones; aristas = conexiones de transmisión confirmadas. |
| Peso | Suma del voltaje nominal de los circuitos en kV. Es un proxy de importancia, no capacidad, flujo, impedancia o riesgo. |
| Objetivo | Maximizar el peso de las aristas que cruzan entre dos zonas. |
| OPT | Mejor corte encontrado por búsqueda exhaustiva; en la instancia de seis nodos evalúa 32 asignaciones por simetría de complemento. |
| Ratio | `cut / OPT`; 1.0 significa que el corte alcanza el óptimo conocido para esa instancia. |
| QAOA esperado | Promedio ponderado por los resultados medidos; no es el mejor bitstring observado. |
| QAOA mejor muestra | Mejor corte entre los bitstrings con conteo positivo; por sí solo no demuestra optimalidad. |

## Archivos críticos, en orden de lectura

| Orden | Ruta | Para qué sirve |
| ---: | --- | --- |
| 1 | `data-analysis/README.md` | Fuente ICE, validación, agregación de circuitos y límites del peso. |
| 2 | `data-analysis/scripts/build_regional_instance.py` | Construye la instancia regional reproducible. |
| 3 | `power-core/artifacts/regional_instance.json` | Contrato de entrada: nodos, aristas, pesos, digest y procedencia. |
| 4 | `power-core/src/optimizer/quantum/qubo/qubo_implementation.py` | Formula el Max-Cut como QUBO. |
| 5 | `power-core/src/optimizer/quantum/ising/ising.py` | Convierte y evalúa la energía Ising completa. |
| 6 | `power-core/src/benchmarks/preliminary.py` | Ejecuta OPT, greedy, GW y QAOA; conserva seeds, fallos y métricas. |
| 7 | `power-core/artifacts/preliminary_local_benchmark/results.json` | Evidencia numérica exacta de la corrida publicada. |
| 8 | `power-core/artifacts/preliminary_local_benchmark/approximation_ratio_vs_p.png` | Evolución del ratio de QAOA según la profundidad `p`. |
| 9 | `power-core/artifacts/preliminary_local_benchmark/method_comparison.png` | Cortes clásicos frente al corte esperado de QAOA para cada `p`. |
| 10 | `power-core/artifacts/preliminary_local_benchmark/qaoa_cut_distribution.png` | Frecuencia con que QAOA produjo cada valor de corte para el mejor `p` preliminar. |
| 11 | `power-core/artifacts/preliminary_local_benchmark/execution_time_comparison.png` | Tiempos observados en escala logarítmica. |
| 12 | `power-core/tests/benchmarks/test_preliminary.py` | Contrato ejecutable de resultados, salidas y preservación de fallos. |

## Cómo leer los gráficos

- `approximation_ratio_vs_p.png`: mirar el ratio esperado, no solo el mejor
  estado. Una sola corrida por profundidad no permite calcular incertidumbre.
- `method_comparison.png`: compara valores sobre **la misma instancia**. QAOA
  aparece mediante su corte esperado; la mejor muestra se excluye para no
  presentarla como rendimiento típico.
- `qaoa_cut_distribution.png`: muestra que encontrar OPT alguna vez no implica
  concentrar alta probabilidad cerca de OPT. La línea esperada resume toda la
  distribución, no solo su extremo.
- `execution_time_comparison.png`: usa escala logarítmica porque los órdenes de
  magnitud son muy distintos. Los tiempos caracterizan este código y entorno;
  no prueban ventaja o desventaja asintótica.
- Si aparece una profundidad fallida, debe permanecer visible en el reporte;
  no se elimina para mejorar la curva.

## Reproducir

```bash
python data-analysis/scripts/build_weighted_graph.py
python data-analysis/scripts/build_regional_instance.py
python power-core/src/benchmarks/preliminary.py \
  --input power-core/artifacts/regional_instance.json \
  --output-dir power-core/artifacts/preliminary_local_benchmark \
  --depths 1 2 3 --parameter-candidates 5 \
  --search-shots 128 --final-shots 1024 --seed 1729 --gw-rounds 128
python -m pytest
```

## Estado y próximos pasos

La corrida preliminar usa una sola corrida independiente por profundidad y
cinco candidatos de parámetros dentro de esa corrida. Por eso no tiene media,
desviación estándar ni barras de error. Para una evaluación final faltan al
menos cinco corridas independientes por configuración, estados del optimizador,
fallos conservados y comparación de dos tamaños si se afirma escalabilidad.

La fuente normativa de restricciones es
[`skills/quantathon-challenge-1/SKILL.md`](../../../skills/quantathon-challenge-1/SKILL.md).
