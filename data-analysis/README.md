# Transmission graph data analysis

The four source files are two logical datasets represented as CSV and GeoJSON. They are versioned snapshots downloaded from the official [ICE Open Data portal](https://datos-ice-se.opendata.arcgis.com/). The transmission-line source is the [ICE transmission lines ArcGIS dataset](https://datos-ice-se.opendata.arcgis.com/datasets/1cd1630e16144d3bbccb1bd434dc6866_0/explore?location=9.946338%2C-83.987696%2C11).

- `Subestaciones.*`: 70 substations. The GeoJSON provides point coordinates;
  both formats are cross-checked by `FID` and shared attributes.
- `LineasDeTransmision.*`: 102 transmission-line records. The GeoJSON provides
  line geometry; both formats are cross-checked by `FID` and shared attributes.

Build the reproducible full weighted graph with:

```bash
python data-analysis/scripts/build_weighted_graph.py
```

The output is `power-core/artifacts/transmission_weighted_graph.json`:
70 nodes, 92 simple undirected edges, 96 resolved line records, and 6 lines
reported as unresolved because at least one named endpoint is outside the
substation dataset. Parallel circuits are aggregated. The edge `weight` is the
sum of nominal circuit voltages in kV; it is a transparent importance proxy,
not capacity, power flow, impedance, or failure risk.

Circuit names are matched after accent normalization, removal of known numeric
parallel-circuit suffixes, and the `Garita`/`La Garita` alias. Every source file
is validated and recorded with a SHA-256 digest in the generated artifact.

The interactive selector lives in `ui/` and exports a 6–12 node GeoJSON
selection.

Build the documented six-node Max-Cut scenario from confirmed transmission
lines with:

```bash
python data-analysis/scripts/build_regional_instance.py
```

Its output is `power-core/artifacts/regional_instance.json`: Pailas,
Liberia, Cañas, Corobicí, Sandillal, and Filadelfia, joined only by confirmed
transmission circuits. It includes a documented synthetic peak-demand baseline;
this is not observed local demand. See
`power-core/docs/spanish/reference-ice-dataset.md` for the source, derivation, and
limitations.

The curated ICE enrichment files add documented planning indicators without
changing the authoritative graph weights:

- `dataset/ice_transmission_enrichment.csv` records line-level voltage,
  published transport-capacity values, planned ranges, emergency values when
  available, DLR installation, source page, and evidence status. Blank MVA
  fields mean that the reviewed public source did not publish a value for that
  exact link; they must not be imputed.
- `dataset/ice_system_indicators.csv` records projected national demand,
  projected energy, transmission length, and total transformation capacity.

The line values come from the ICE Plan de Expansión de la Transmisión
2024-2034. They are planning/documentation values, not a real-time flow
dataset. Use MVA as a Max-Cut weight only after matching every edge in an
instance; otherwise retain `sum_nominal_voltage_kv` and report MVA as a
secondary enrichment.

The older geographic fallback is available only when explicitly requested:

```bash
python data-analysis/scripts/build_regional_instance.py \
  --mode proximity-fallback --province Guanacaste --count 6 --neighbors 2
```

Its `edge_model` and limitation fields must be included in any report; inferred
proximity is not a claim about the real electrical topology.

Render the exact six-node graph used by the QUBO/Max-Cut instance with:

```bash
python data-analysis/scripts/plot_regional_graph.py
```

This writes `power-core/artifacts/regional_instance_graph.png`. Node positions
use the dataset coordinates, edge labels show the nominal-voltage weights, and
the reference two-zone cut is highlighted in red.
