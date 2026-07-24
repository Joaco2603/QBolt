# Benchmark local preliminar — Challenge 1

> **Estado: `preliminary`.** Esta evidencia no es un benchmark final ni demuestra convergencia, ventaja cuántica o superioridad sobre Goemans–Williamson.

## Reproducción

```bash
python power-core/src/benchmarks/preliminary.py --input /tmp/quantum-power-benchmark-inputs/regional_instance_12.json --output-dir power-core/artifacts/preliminary_local_benchmark_12_escalated --depths 1 2 3 --parameter-candidates 5 --search-shots 128 --final-shots 1024 --seed 1729 --gw-rounds 128
```

- Input: `/tmp/quantum-power-benchmark-inputs/regional_instance_12.json`
- SHA-256: `d07bf012aac74fdcf3b9db062edcf6d157763952c11b1e635e130198c23317b8`
- Grafo: 12 nodos, 14 aristas
- OPT exacto: 2.0296
- Backend QAOA: `guppy-selene`
- Semilla base: `1729`
- Shots de búsqueda/finales: `128` / `1024`

## Resultados

| Método | Configuración | Expected cut | Mejor cut muestreado | Ratio esperado / OPT | Estado | Tiempo (s) |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Exacto | fuerza bruta | 2.0296 | 2.0296 | 1 | completed | 0.024959 |
| Greedy | seed=1729 | 2.0296 | 2.0296 | 1 | completed | 0.000285 |
| GW | seed=1730, rounds=128 | 2.0296 | 2.0296 | 1 | completed | 0.030616 |
| QAOA local | p=1 | 1.14347 | 2.0296 | 0.563397 | completed | 10.6974 |
| QAOA local | p=2 | 1.2659 | 2.0296 | 0.623721 | completed | 16.2214 |
| QAOA local | p=3 | 1.4259 | 1.98226 | 0.702553 | completed | 23.2305 |

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
