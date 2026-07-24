# De datos nacionales a un escenario regional reproducible

Este documento separa la evidencia oficial de Costa Rica de los supuestos del
escenario de seis subestaciones usado en el benchmark de Max-Cut. Esa separación
evita presentar estimaciones regionales como mediciones de ICE.

## Decisión del escenario

El escenario usa seis subestaciones de Guanacaste conectadas por cinco líneas de
transmisión confirmadas en `LineasDeTransmision.*`:

| Subestaciones conectadas | Voltaje nominal |
| --- | ---: |
| Pailas — Liberia | 230 kV |
| Liberia — Cañas | 230 kV |
| Cañas — Corobicí | 230 kV |
| Corobicí — Sandillal | 230 kV |
| Cañas — Filadelfia | 138 kV |

La selección reemplaza el anterior fallback por proximidad geográfica. Unir
subestaciones cercanas no prueba que exista una línea eléctrica entre ellas;
por eso solo se usan circuitos confirmados por el dataset.

Max-Cut divide estas seis subestaciones en **dos zonas**. La partición de
referencia `{Pailas, Cañas, Sandillal}` y `{Liberia, Corobicí, Filadelfia}`
corta las cinco líneas, con peso de referencia de **1.058 kV**. El peso es la
suma de voltajes nominales: es un proxy reproducible de importancia, no una
capacidad eléctrica ni un flujo de potencia.

## Datos oficiales del Sistema Eléctrico Nacional, 2025

Los valores son nacionales y corresponden al último año completo del informe
de la División de Operación y Control del Sistema Eléctrico (DOCSE) del ICE.

| Indicador | Resultado |
| --- | ---: |
| Capacidad instalada | 3.658,6 MW |
| Producción eléctrica | 13.352,94 GWh |
| Demanda nacional | 12.995,44 GWh |
| Demanda máxima del sistema | 1.940,23 MW |
| Importación para atender demanda | 174,80 GWh |
| Producción renovable | 98,6 % |
| Demanda atendida con renovables | 97,3 % |

| Fuente de generación | Producción 2025 |
| --- | ---: |
| Hidroeléctrica | 10.098,59 GWh |
| Eólica | 1.550,36 GWh |
| Geotérmica | 1.430,18 GWh |
| Termoeléctrica | 181,27 GWh |
| Bagazo | 55,91 GWh |
| Solar | 36,62 GWh |

La producción incluye exportaciones. Las importaciones comerciales del ICE
(180,05 GWh) no son intercambiables con los 174,80 GWh contabilizados para
atender la demanda nacional: son indicadores distintos.

### Demanda mensual nacional

| Mes | Demanda |
| --- | ---: |
| Enero | 1.063,53 GWh |
| Febrero | 993,60 GWh |
| Marzo | 1.133,35 GWh |
| Abril | 1.079,93 GWh |
| Mayo | 1.123,04 GWh |
| Junio | 1.067,59 GWh |
| Julio | 1.106,56 GWh |
| Agosto | 1.102,62 GWh |
| Septiembre | 1.067,69 GWh |
| Octubre | 1.103,55 GWh |
| Noviembre | 1.072,56 GWh |
| Diciembre | 1.081,43 GWh |
| **Total** | **12.995,44 GWh** |

Marzo fue el mes de mayor demanda acumulada. No debe confundirse con el pico
instantáneo: la demanda máxima de 1.940,23 MW ocurrió el 8 de abril.

### Compras comerciales del ICE en el Mercado Eléctrico Regional

| Mes | Compras |
| --- | ---: |
| Enero | 0 GWh |
| Febrero | 5,82 GWh |
| Marzo | 80,25 GWh |
| Abril | 22,75 GWh |
| Mayo | 0 GWh |
| Junio | 0 GWh |
| Julio | 0 GWh |
| Agosto | 0,80 GWh |
| Septiembre | 29,33 GWh |
| Octubre | 5,38 GWh |
| Noviembre | 0 GWh |
| Diciembre | 35,73 GWh |
| **Total comercial ICE** | **180,05 GWh** |

## Carga sintética calibrada

El dataset de red contiene 70 subestaciones, su ubicación y líneas con voltaje
nominal; **no** contiene demanda por cantón, subestación ni hora. Por tanto,
`synthetic_peak_demand_mw` no es una observación local.

Se usa un baseline uniforme y trazable:

```text
27,717571 MW por subestación = 1.940,23 MW de demanda máxima nacional / 70 subestaciones
166,305429 MW en el escenario = 6 × 27,717571 MW
```

La distribución uniforme es deliberada: no existe en este repositorio una
fuente que justifique asignar mayor demanda a una de estas seis subestaciones.
El campo entrega una escala realista en MW para experimentos futuros sin
afirmar una demanda medida para Liberia, Cañas o Carrillo. El Max-Cut base no
usa este campo en su objetivo; usa únicamente los pesos de las líneas.

## Datos que aún faltan

Para un modelo operativo —y no solo un benchmark de partición— se requiere:

- demanda horaria y demanda máxima por subestación o cantón;
- capacidad térmica (MVA/MW), impedancia, flujos y dirección de cada línea;
- generación, disponibilidad y punto de conexión por planta;
- estado operativo, mantenimientos, fallas y cargas críticas.

Hasta contar con esas fuentes, no se deben interpretar los resultados como un
plan de restauración real ni como capacidad de suministro de una zona.

## Fuentes

- [Portal de Datos Abiertos del ICE](https://datos-ice-se.opendata.arcgis.com/) — catálogo oficial del que se obtuvieron las copias versionadas de entrada en `data-analysis/dataset/`.
- [ICE Datos Abiertos — Subestaciones](https://datos-ice-se.opendata.arcgis.com/datasets/f3fceca2659b4ecf8a5c2632e04aff1f_0/explore?location=9.942788%2C-84.130603%2C13&showTable=true) — fuente geoespacial declarada del dataset `Subestaciones.*`. El servicio lo describe como un levantamiento georreferenciado de los sitios de subestaciones; cada punto es el centroide aproximado del patio de equipos, no la ubicación exacta de cada activo. La División de Transmisión indica actualización anual y levantamientos LiDAR aéreos.
- [ICE Datos Abiertos — Líneas de transmisión](https://datos-ice-se.opendata.arcgis.com/datasets/1cd1630e16144d3bbccb1bd434dc6866_0/explore?location=9.946338%2C-83.987696%2C11) — fuente del dataset `LineasDeTransmision.*`, incluido el campo `Voltaje` del que se obtienen los pesos del grafo.
- [ICE DOCSE — Informe de atención de demanda y producción de electricidad con fuentes renovables, Costa Rica 2025](https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf)
- [ICE DOCSE — Informe Anual 2025](https://apps.grupoice.com/CenceWeb/documentos/3/3008/28/Informe%20Anual%202025.pdf)
- `data-analysis/dataset/Subestaciones.{csv,geojson}` y `data-analysis/dataset/LineasDeTransmision.{csv,geojson}`
