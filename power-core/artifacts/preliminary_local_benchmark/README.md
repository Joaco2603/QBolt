# Benchmark local preliminar — Challenge 1

> **Estado: `preliminary`.** Esta evidencia no es un benchmark final ni demuestra convergencia, ventaja cuántica o superioridad sobre Goemans–Williamson.

## Reproducción

```bash
python power-core/src/benchmarks/preliminary.py --input power-core/artifacts/regional_instance.json --output-dir power-core/artifacts/preliminary_local_benchmark --depths 1 2 3 --parameter-candidates 5 --search-shots 128 --final-shots 1024 --seed 1729 --gw-rounds 128
```

- Input: `power-core/artifacts/regional_instance.json`
- SHA-256: `b0cbdf2b81240aba24513c78c475a129dcdfafe6f588c790282a40bfacd24674`
- Grafo: 6 nodos, 5 aristas
- OPT exacto: 1058
- Backend QAOA: `guppy-selene`
- Semilla base: `1729`
- Shots de búsqueda/finales: `128` / `1024`

## Resultados

| Método | Configuración | Expected cut | Mejor cut muestreado | Ratio esperado / OPT | Estado | Tiempo (s) |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Exacto | fuerza bruta | 1058 | 1058 | 1 | completed | 7.5e-05 |
| Greedy | seed=1729 | 1058 | 1058 | 1 | completed | 5.3e-05 |
| GW | seed=1730, rounds=128 | 1058 | 1058 | 1 | completed | 0.010248 |
| QAOA local | p=1 | 511.48 | 1058 | 0.483441 | completed | 4.60457 |
| QAOA local | p=2 | 632.725 | 1058 | 0.598038 | completed | 3.00138 |
| QAOA local | p=3 | 592.16 | 1058 | 0.559698 | completed | 3.49828 |

`approximation_ratio_vs_p.png` muestra el ratio de QAOA por profundidad; `method_comparison.png` compara el corte esperado de QAOA contra OPT y los métodos clásicos; `qaoa_cut_distribution.png` muestra con qué frecuencia apareció cada corte para la mejor profundidad preliminar; y `execution_time_comparison.png` caracteriza los tiempos medidos. La mejor muestra QAOA no se usa como rendimiento típico. No incluyen barras de error porque hay una sola corrida independiente por configuración.

## Búsqueda aleatoria de parámetros

Para cada capa, `gamma_l ~ Uniform(0, pi / max_abs_J), where max_abs_J = max_(i,j) |J_ij|; if max_abs_J = 0, gamma_l = 0`. En esta instancia `max_abs_J = 115`. Se usa `beta_l ~ Uniform(0, pi / 2)`.

Cada `p` usa **5 candidatos de parámetros dentro de UNA corrida independiente**. Estos candidatos no son 5 corridas independientes. Se selecciona el candidato de mayor `expected_cut` durante búsqueda y luego se vuelve a muestrear con shots finales. Los estados con count cero se excluyen de métricas y outputs.

## Fallos conservados

Ninguna profundidad falló.

## Limitaciones

- Solo hay una corrida independiente por `p`; no se reportan media, desviación estándar ni barras de error.
- Los cinco candidatos predeterminados son pruebas de parámetros, no las cinco inicializaciones/corridas independientes exigidas para la evaluación final.
- La búsqueda aleatoria pequeña no permite afirmar convergencia del QAOA.
- `LocalGuppySeleneBackend` recompila el programa Guppy en cada evaluación; los tiempos caracterizan esta implementación preliminar y no ventaja computacional.
- Los shots provienen de emulación local, no de hardware cuántico físico ni de emulación H2.
- Pesos (`kV`): Each edge weight is the summed nominal voltage of confirmed circuits between its two substations. No deben reinterpretarse como otra magnitud física.
- No se afirma ventaja cuántica ni superioridad sobre Goemans–Williamson.
- Antes de considerar el benchmark listo para entrega se requieren al menos cinco corridas independientes por configuración y sus estadísticas.

## Archivos

- `results.json`: configuración, versiones, seeds, counts positivos, parámetros, tiempos, métricas y fallos.
- `approximation_ratio_vs_p.png`: ratio contra profundidad sin barras de error.
- `method_comparison.png`: comparación visual honesta; QAOA usa `expected_cut`, no su mejor muestra.
- `qaoa_cut_distribution.png`: distribución de probabilidad empírica de los cortes en la profundidad con mayor `expected_cut`.
- `execution_time_comparison.png`: tiempos observados en escala logarítmica; caracterizan esta implementación, no una ventaja computacional.
- `README.md`: este resumen reproducible.
