"""Checks for the curated ICE transmission enrichment tables."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).parents[2]
DATASET = ROOT / "data-analysis" / "dataset"


def read_table(name: str) -> list[dict[str, str]]:
    with (DATASET / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_ice_line_enrichment_preserves_explicit_missing_capacity() -> None:
    rows = read_table("ice_transmission_enrichment.csv")
    assert len(rows) == 6
    pailas_liberia = next(
        row for row in rows
        if {row["source_endpoint"], row["target_endpoint"]} == {"Pailas", "Liberia"}
    )
    assert pailas_liberia["capacity_mva_current"] == ""
    assert pailas_liberia["record_status"] == "dlr_only"
    assert pailas_liberia["source_url"].startswith("https://www.grupoice.com/")


def test_ice_line_enrichment_contains_documented_capacity_ranges() -> None:
    rows = read_table("ice_transmission_enrichment.csv")
    liberia_canas = next(
        row for row in rows
        if {row["source_endpoint"], row["target_endpoint"]} == {"Liberia", "Cañas"}
    )
    assert liberia_canas["capacity_mva_current"] == "400"
    assert liberia_canas["capacity_mva_planned_max"] == "700"


def test_ice_system_indicators_cover_pet_projection_horizon() -> None:
    rows = read_table("ice_system_indicators.csv")
    assert [int(row["year"]) for row in rows] == list(range(2024, 2035))
    assert rows[0]["transmission_length_km"] == "2995.7"
    assert rows[-1]["projected_demand_mw"] == "2088"
