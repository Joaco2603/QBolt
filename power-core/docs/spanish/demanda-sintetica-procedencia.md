# Procedencia de la demanda sintética del escenario regional

Este documento explica de dónde proviene el campo
`synthetic_peak_demand_mw` del archivo
`power-core/artifacts/regional_instance.json`, cómo se calcula y, sobre todo,
qué **no** representa.

## Resumen

El dataset geoespacial de red contiene subestaciones y líneas de transmisión,
pero no contiene demanda eléctrica medida por subestación, cantón u hora. Para
poder disponer de una escala en MW en experimentos posteriores, el escenario
asigna a cada subestación la misma fracción de la demanda máxima nacional.

```text
Demanda sintética por subestación = demanda máxima nacional / número de subestaciones del dataset
```

Esta es una asignación uniforme, calibrada con un indicador oficial nacional.
No es una observación local de demanda.

## Fuente observada

El único valor observado usado en el cálculo es la demanda máxima nacional de
Costa Rica para 2025:

| Campo | Valor | Unidad | Procedencia |
|---|---:|---|---|
| Demanda máxima nacional | 1.940,23 | MW | ICE DOCSE, Informe de atención de demanda y producción de electricidad con fuentes renovables, Costa Rica 2025 |
| Número de subestaciones del dataset | 70 | subestaciones | `data-analysis/dataset/Subestaciones.{csv,geojson}` |

Fuente del indicador nacional:

- [ICE DOCSE — Informe de atención de demanda y producción de electricidad con fuentes renovables, Costa Rica 2025](https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf)

El pico nacional ocurrió el 8 de abril de 2025. No debe confundirse con la
demanda anual acumulada, que se mide en GWh, ni con la capacidad instalada.

## Cálculo reproducible

El generador define:

```python
NATIONAL_PEAK_DEMAND_MW = 1940.23
```

Después obtiene el número de nodos del grafo nacional validado y realiza:

```text
1.940,23 MW / 70 subestaciones = 27,717571 MW por subestación
```

El escenario regional contiene seis nodos. Por ello, su suma sintética es:

```text
6 × 27,717571 MW = 166,305429 MW
```

| Resultado | Valor |
|---|---:|
| `synthetic_peak_demand_mw` por nodo | 27,717571 MW |
| Nodos del escenario regional | 6 |
| Total sintético del escenario | 166,305429 MW |

El valor se redondea a seis decimales al escribir cada nodo en el artefacto.

## Cómo se genera el artefacto

La lógica está en:

```text
data-analysis/scripts/build_regional_instance.py
```

En el modo predeterminado `confirmed`, el script:

1. carga los pares CSV y GeoJSON de subestaciones y líneas;
2. valida que las conexiones del escenario sean líneas de transmisión
   confirmadas;
3. construye el grafo nacional, que actualmente contiene 70 subestaciones;
4. selecciona Pailas, Liberia, Cañas, Corobicí, Sandillal y Filadelfia;
5. divide `1.940,23 MW` entre los 70 nodos nacionales;
6. asigna el resultado uniforme a los seis nodos seleccionados como
   `synthetic_peak_demand_mw`;
7. registra la fórmula, la fuente y la advertencia en el bloque
   `synthetic_demand` del JSON generado.

Para regenerar el artefacto desde la raíz del repositorio:

```bash
python data-analysis/scripts/build_regional_instance.py
```

## Qué significa el campo

`synthetic_peak_demand_mw` significa:

> Una escala hipotética y uniforme en MW, derivada de la demanda máxima
> nacional y distribuida por igual entre las subestaciones del dataset.

Puede servir para prototipos, por ejemplo para ensayar una futura restricción
de balance de carga. Debe etiquetarse siempre como **sintético**.

## Qué no significa

El campo **no** demuestra que Pailas, Liberia, Cañas, Corobicí, Sandillal o
Filadelfia tengan exactamente 27,717571 MW de demanda máxima.

Tampoco representa:

- demanda medida en una subestación;
- demanda por cantón o distrito;
- consumo horario;
- potencia que circula por una línea;
- capacidad térmica de una línea o transformador;
- generación conectada a cada nodo;
- carga crítica atendida por una subestación.

El Max-Cut base no usa este campo: su objetivo usa únicamente el peso de las
líneas, definido como la suma de voltajes nominales de los circuitos
confirmados.

## Limitación del supuesto uniforme

La asignación uniforme se escogió porque este repositorio no contiene una
fuente verificable para afirmar que una subestación tiene más demanda que otra.
Asignar valores distintos según intuición, tamaño aparente o cercanía geográfica
crearía datos inventados y haría difícil reproducir o defender el modelo.

La uniformidad evita ese sesgo, pero no vuelve realista la distribución. Es una
hipótesis de partida, no un resultado de ICE.

## Datos necesarios para sustituirla

Para reemplazar esta aproximación por demanda modelada u observada se requeriría
al menos una fuente con alguno de estos datos:

| Dato requerido | Granularidad deseable |
|---|---|
| Demanda máxima | Por subestación o cantón |
| Perfil de demanda | Horario por subestación o cantón |
| Cargas críticas | Por instalación o zona |
| Generación conectada | Por planta y subestación |
| Capacidad de líneas y transformadores | MVA/MW por activo |
| Estado operativo y mantenimientos | Por activo y periodo |

Hasta obtenerlos, cualquier resultado que use `synthetic_peak_demand_mw` debe
presentarse como un experimento de escenario, no como una recomendación de
operación o restauración de la red.

## Referencias internas

- `power-core/artifacts/regional_instance.json` — valor generado y metadatos
  `synthetic_demand`.
- `data-analysis/scripts/build_regional_instance.py` — cálculo y generación
  reproducible.
- `data-analysis/tests/test_build_regional_instance.py` — prueba que verifica
  la fórmula `1.940,23 / 70` y el total de seis nodos.
- `power-core/docs/spanish/reference-ice-dataset.md` — contexto de datos
  nacionales, topología regional y limitaciones.
