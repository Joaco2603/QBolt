# Provenance of the regional scenario's synthetic demand

This document explains where the `synthetic_peak_demand_mw` field in
`power-core/artifacts/regional_instance.json` comes from, how it is calculated,
and, most importantly, what it **does not** represent.

## Summary

The geospatial grid dataset contains substations and transmission lines, but it
does not contain measured electricity demand per substation, canton, or hour.
To provide an MW scale for later experiments, the scenario assigns every
substation the same share of national peak demand.

```text
Synthetic demand per substation = national peak demand / number of dataset substations
```

This is a uniform allocation calibrated with an official national indicator. It
is not a local demand observation.

## Observed source

The only observed value used in the calculation is Costa Rica's 2025 national
peak demand:

| Field | Value | Unit | Source |
|---|---:|---|---|
| National peak demand | 1,940.23 | MW | ICE DOCSE, *Informe de atención de demanda y producción de electricidad con fuentes renovables, Costa Rica 2025* |
| Dataset substation count | 70 | substations | `data-analysis/dataset/Subestaciones.{csv,geojson}` |

Source for the national indicator:

- [ICE DOCSE — Informe de atención de demanda y producción de electricidad con fuentes renovables, Costa Rica 2025](https://apps.grupoice.com/CenceWeb/documentos/3/3008/27/R01-PDOCSE-07%20Informe_Atenci%C3%B3n%20demanda%20y%20producci%C3%B3n_2025_v2_firmado.pdf)

The national peak occurred on 8 April 2025. It must not be confused with annual
accumulated demand, measured in GWh, or with installed capacity.

## Reproducible calculation

The generator defines:

```python
NATIONAL_PEAK_DEMAND_MW = 1940.23
```

It then obtains the node count of the validated national graph and calculates:

```text
1,940.23 MW / 70 substations = 27.717571 MW per substation
```

The regional scenario contains six nodes, so its synthetic total is:

```text
6 × 27.717571 MW = 166.305429 MW
```

| Result | Value |
|---|---:|
| `synthetic_peak_demand_mw` per node | 27.717571 MW |
| Regional scenario nodes | 6 |
| Synthetic scenario total | 166.305429 MW |

The value is rounded to six decimal places when each node is written to the
artifact.

## How the artifact is generated

The implementation is in:

```text
data-analysis/scripts/build_regional_instance.py
```

In its default `confirmed` mode, the script:

1. loads the substation and transmission-line CSV/GeoJSON source pairs;
2. validates that the scenario connections are confirmed transmission lines;
3. builds the national graph, which currently contains 70 substations;
4. selects Pailas, Liberia, Cañas, Corobicí, Sandillal, and Filadelfia;
5. divides `1,940.23 MW` by the 70 national graph nodes;
6. assigns that uniform result to the six selected nodes as
   `synthetic_peak_demand_mw`;
7. records the formula, source, and warning in the generated JSON's
   `synthetic_demand` block.

To regenerate the artifact from the repository root:

```bash
python data-analysis/scripts/build_regional_instance.py
```

## What the field means

`synthetic_peak_demand_mw` means:

> A uniform hypothetical MW scale derived from national peak demand and split
equally across the dataset's substations.

It can support prototypes, for example a future load-balance constraint. It
must always be labelled **synthetic**.

## What the field does not mean

The field does **not** establish that Pailas, Liberia, Cañas, Corobicí,
Sandillal, or Filadelfia each have exactly 27.717571 MW of peak demand.

It also does not represent:

- measured demand at a substation;
- demand per canton or district;
- hourly consumption;
- power flowing through a transmission line;
- thermal capacity of a line or transformer;
- generation connected to a node;
- critical load served by a substation.

The baseline Max-Cut model does not use this field. Its objective uses only the
line weights, which are defined as the summed nominal voltages of confirmed
circuits.

## Limitation of the uniform assumption

The uniform allocation was chosen because this repository does not include a
verifiable source that supports assigning higher demand to one substation than
to another. Assigning different values from intuition, apparent size, or
geographic proximity would create invented data and make the model harder to
reproduce or defend.

Uniformity avoids that unsupported bias, but it does not make the distribution
realistic. It is a starting assumption, not an ICE result.

## Data needed to replace it

Replacing this approximation with measured or modelled demand requires a source
for at least some of the following:

| Required data | Preferred granularity |
|---|---|
| Peak demand | Per substation or canton |
| Demand profile | Hourly per substation or canton |
| Critical loads | Per facility or area |
| Connected generation | Per plant and substation |
| Line and transformer capacity | MVA/MW per asset |
| Operating state and maintenance | Per asset and period |

Until such data are available, any result using `synthetic_peak_demand_mw` must
be presented as a scenario experiment, not as an operating or restoration
recommendation for the grid.

## Internal references

- `power-core/artifacts/regional_instance.json` — generated value and
  `synthetic_demand` metadata.
- `data-analysis/scripts/build_regional_instance.py` — reproducible calculation
  and artifact generator.
- `data-analysis/tests/test_build_regional_instance.py` — test verifying the
  `1,940.23 / 70` formula and the six-node total.
- `power-core/docs/english/reference-ice-dataset.md` — national-data context,
  regional topology, and limitations.
