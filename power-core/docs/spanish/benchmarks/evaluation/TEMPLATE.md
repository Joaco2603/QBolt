# Evaluación vNNN — <título corto>

> Estado: `planned` | `running` | `completed` | `invalidated`
>
> Fecha: `YYYY-MM-DD`

## Objetivo

<!-- Qué hipótesis o comparación responde esta evaluación. -->

## Alcance y cambios respecto de la versión anterior

- Instancia: `<artifact path o identifier>`
- Cambio principal: `<qué cambió; usar "primera evaluación" para v001>`
- No cambia: `<condiciones que permanecen comparables>`
- Fuera de alcance: `<qué no permite concluir esta versión>`

## Procedencia y reproducibilidad

| Campo | Valor |
| --- | --- |
| Artefacto de grafo | `<path>` |
| Digest de fuente / artefacto | `<sha256>` |
| Nodos / aristas | `<n> / <m>` |
| Convención de objetivo | `<Max-Cut a maximizar / energía Ising a minimizar>` |
| Convención QUBO/Ising validada | `<sí/no; enlace a evidencia>` |
| Entorno y dependencias | `<Python, paquetes y versiones>` |
| Hardware | `<CPU/RAM/SO o N/A>` |
| Comando de reproducción | `<comando completo>` |

## Configuración experimental

| Solucionador | Configuración | Semillas / inicializaciones | Presupuesto |
| --- | --- | --- | --- |
| Exhaustivo | `<enumeración o N/A>` | `determinista` | `<número de cortes>` |
| Greedy | `<regla de desempate>` | `<semillas o N/A>` | `<reinicios>` |
| Goemans-Williamson | `<solver SDP, tolerancia, rounds>` | `<semillas>` | `<rounds>` |
| QAOA | `<p, optimizador, backend, shots>` | `<mínimo cinco>` | `<evaluaciones / shots>` |
| Extra: `<nombre>` | `<configuración>` | `<semillas>` | `<presupuesto>` |

## Resultados

### Referencia exacta

| Métrica | Valor |
| --- | --- |
| `OPT` | `<valor>` |
| Partición óptima canónica | `<partición>` |
| Método | `<búsqueda exhaustiva / otro, con justificación>` |

> Si `OPT = 0`, los ratios se reportan como `N/A`; nunca como `0/0`.

### Tabla comparativa

| Solucionador | Configuración | Mejor cut | Media | Desv. est. | Ratio contra `OPT` | Estado | Tiempo | Evidencia |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |
| Greedy | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<archivo>` |
| GW | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<archivo>` |
| QAOA | `p=<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<archivo>` |
| Extra | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<archivo>` |

Para métodos estocásticos, conservar el detalle de **cada** semilla/corrida en
un archivo tabular versionado dentro de esta carpeta.

### QAOA por profundidad

| `p` | Inicializaciones | Media de ratio | Desv. est. | Mejor ratio | Corridas no convergentes/fallidas | Backend / shots |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `<1>` | `<>=5>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

- Figura `r` frente a `p`: `<path o pendiente>`
- Tamaños comparados: `<lista; obligatorio solo para afirmaciones de escalabilidad>`

## Corridas fallidas o no convergentes

| Solucionador | Semilla | Configuración | Estado | Error o diagnóstico | Tratamiento |
| --- | ---: | --- | --- | --- | --- |
| `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<se conserva; no se sustituye silenciosamente>` |

## Interpretación y limitaciones

- `<Qué permite concluir la evidencia>`
- `<Qué no permite concluir>`
- `<Efecto de ruido, emulación, tolerancias SDP o sensibilidad de semillas>`
- No afirmar ventaja cuántica ni superioridad sobre Goemans-Williamson.
- Si se usó emulación H2, describirla como emulación, no como hardware físico.

## Artefactos

- `<archivo de resultados>`
- `<figura>`
- `<log o configuración>`
- `<commit hash>`
