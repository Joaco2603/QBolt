# Benchmark local preliminar — Challenge 1

> **Estado: `preliminary`.** Esta evidencia no es un benchmark final ni demuestra convergencia, ventaja cuántica o superioridad sobre Goemans–Williamson.

## Reproducción

```bash
python power-core/src/benchmarks/preliminary.py --input /tmp/quantum-power-benchmark-inputs/regional_instance_10.json --output-dir power-core/artifacts/preliminary_local_benchmark_10_escalated --depths 1 2 3 --parameter-candidates 5 --search-shots 128 --final-shots 1024 --seed 1729 --gw-rounds 128
```

- Input: `/tmp/quantum-power-benchmark-inputs/regional_instance_10.json`
- SHA-256: `5bccf24ec650f365a0ff8aa6edb82b960847929d9e5a4ac458cecd9a67067019`
- Grafo: 10 nodos, 13 aristas
- OPT exacto: 1.86666
- Backend QAOA: `guppy-selene`
- Semilla base: `1729`
- Shots de búsqueda/finales: `128` / `1024`

## Resultados

| Método | Configuración | Expected cut | Mejor cut muestreado | Ratio esperado / OPT | Estado | Tiempo (s) |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Exacto | fuerza bruta | 1.86666 | 1.86666 | 1 | completed | 0.006576 |
| Greedy | seed=1729 | 1.80479 | 1.80479 | 0.966856 | completed | 0.000325 |
| GW | seed=1730, rounds=128 | 1.86666 | 1.86666 | 1 | completed | 0.032476 |
| QAOA local | p=1 | 1.02344 | 1.86666 | 0.548274 | completed | 5.47823 |
| QAOA local | p=2 | 1.13644 | 1.86666 | 0.60881 | completed | 7.1071 |
| QAOA local | p=3 | 1.05837 | 1.86666 | 0.566985 | completed | 9.12555 |

La figura `approximation_ratio_vs_p.png` muestra los ratios esperado y del mejor estado muestreado. No incluye barras de error porque hay una sola corrida independiente por configuración.

## Búsqueda aleatoria de parámetros

Para cada capa, `gamma_l ~ Uniform(0, pi / max_abs_J), where max_abs_J = max_(i,j) |J_ij|; if max_abs_J = 0, gamma_l = 0`. En esta instancia `max_abs_J = 0.446981`. Se usa `beta_l ~ Uniform(0, pi / 2)`.

Cada `p` usa **5 candidatos de parámetros dentro de UNA corrida independiente**. Estos candidatos no son 5 corridas independientes. Se selecciona el candidato de mayor `expected_cut` durante búsqueda y luego se vuelve a muestrear con shots finales. Los estados con count cero se excluyen de métricas y outputs.

## Fallos conservados

Ninguna profundidad falló.

## Limitaciones

- Solo hay una corrida independiente por `p`; no se reportan media, desviación estándar ni barras de error.
- Los cinco candidatos predeterminados son pruebas de parámetros, no las cinco inicializaciones/corridas independientes exigidas para la evaluación final.
- La búsqueda aleatoria pequeña no permite afirmar convergencia del QAOA.
- `LocalGuppySeleneBackend` recompila el programa Guppy en cada evaluación; los tiempos caracterizan esta implementación preliminar y no ventaja computacional.
- Los shots provienen de emulación local, no de hardware cuántico físico ni de emulación H2.
- El peso es suma de voltaje nominal (kV): es un proxy de importancia, no capacidad, flujo, impedancia ni riesgo.
- No se afirma ventaja cuántica ni superioridad sobre Goemans–Williamson.
- Antes de considerar el benchmark listo para entrega se requieren al menos cinco corridas independientes por configuración y sus estadísticas.

## Archivos

- `results.json`: configuración, versiones, seeds, counts positivos, parámetros, tiempos, métricas y fallos.
- `approximation_ratio_vs_p.png`: ratio contra profundidad sin barras de error.
- `README.md`: este resumen reproducible.
