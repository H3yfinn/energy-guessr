#!/usr/bin/env python3
"""
Lightweight extractor for the Energy Institute Stats Review workbook.

This builds a JSON in the same shape as the UN/APEC datasets, but only uses the
fuel breakdowns available in the EI workbook (currently 2023 & 2024) and
converts everything to PJ.

Example:
python scripts/create_ei_assets.py \\
  --input EI-Stats-Review-ALL-data.xlsx \\
  --output-json public/data/energy-profiles-ei.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Mapping

import pandas as pd

# Reuse helpers from the main prep script to keep the output structure identical
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for p in (SCRIPT_DIR, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.append(str(p))
import create_energy_assets as prep  # type: ignore  # noqa: E402

# Column mappings from EI sheet labels -> app fuel keys
SUPPLY_FUEL_MAP: Mapping[str, str] = {
    "Oil": "oil",
    "Natural Gas": "gas",
    "Coal": "coal",
    "Nuclear energy": "nuclear",
    "Hydro electric": "hydro",
    "Renew- ables": "renewables_and_others",
}

ELEC_FUEL_MAP: Mapping[str, str] = {
    "Oil": "oil",
    "Natural Gas": "gas",
    "Coal": "coal",
    "Nuclear energy": "nuclear",
    "Hydro electric": "hydro",
    "Renewables": "renewables_and_others",
    "Other#": "renewables_and_others",
}

# The EI "by fuel" sheets publish 2023 in the base columns and 2024 in the ".1"
# suffixed columns. Keep both so the app can offer a year toggle.
YEAR_SUFFIXES: Mapping[int, str] = {2023: "", 2024: ".1"}


def _slugify_economy(name: str) -> str:
    """
    Turn free-text economy names into stable codes.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return f"EI_{slug.upper()}"


def _read_by_fuel_sheet(
    workbook: Path,
    sheet: str,
    fuel_map: Mapping[str, str],
    unit_to_pj: float,
    year_suffixes: Mapping[int, str],
) -> Dict[int, Dict[str, Dict[str, float]]]:
    """
    Parse an EI sheet with the common layout:
    - title row
    - blank row
    - header row with fuels (row index 2 when 0-based)
    - blank spacer
    - data rows
    Returns {year: {economy_code: {fuel: value_pj}}}
    """
    df = pd.read_excel(workbook, sheet_name=sheet, header=2)
    if df.empty:
        raise RuntimeError(f"No data found in sheet {sheet}")

    # First column contains the economy name
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "economy"})
    df = df.dropna(subset=["economy"])

    # Keep only columns we know how to map
    columns_needed: set[str] = set()
    for raw in fuel_map.keys():
        for suffix in year_suffixes.values():
            col = raw + suffix
            if col in df.columns:
                columns_needed.add(col)
    missing = [c for c in fuel_map.keys() if all((c + suf) not in df.columns for suf in year_suffixes.values())]
    if missing:
        raise RuntimeError(f"Missing expected columns in {sheet}: {missing}")
    keep_cols = ["economy"] + sorted(columns_needed)
    df = df[keep_cols]

    out: Dict[int, Dict[str, Dict[str, float]]] = {year: {} for year in year_suffixes.keys()}
    for _, row in df.iterrows():
        econ_label = str(row["economy"]).strip()
        if not econ_label:
            continue
        econ_code = _slugify_economy(econ_label)
        for year, suffix in year_suffixes.items():
            fuels: Dict[str, float] = out.setdefault(year, {}).setdefault(econ_code, {})
            for raw, mapped in fuel_map.items():
                col = raw + suffix
                if col not in row:
                    continue
                val = pd.to_numeric(row[col], errors="coerce")
                if pd.isna(val):
                    continue
                fuels[mapped] = float(val) * unit_to_pj + fuels.get(mapped, 0.0)
        # Store the prettified name once (used later when building profiles)
        out.setdefault(-1, {})[econ_code] = {"name": econ_label}  # sentinel bucket
    return out


def _merge_sector_data(
    supply: Dict[int, Dict[str, Dict[str, float]]],
    elec: Dict[int, Dict[str, Dict[str, float]]],
) -> Dict[int, Dict[str, Dict[str, List[Dict[str, float]]]]]:
    """
    Combine sector maps from supply and electricity into the shape expected by the app.
    """
    years = set(supply.keys()) | set(elec.keys())
    years.discard(-1)  # sentinel bucket used for names

    by_year: Dict[int, Dict[str, Dict[str, List[Dict[str, float]]]]] = {}
    for year in years:
        sector_map: Dict[str, Dict[str, List[Dict[str, float]]]] = {}
        economies = set()
        if year in supply:
            economies.update(supply[year].keys())
        if year in elec:
            economies.update(elec[year].keys())
        for econ in economies:
            sectors: Dict[str, List[Dict[str, float]]] = {}
            if year in supply and econ in supply[year]:
                sectors["07_total_primary_energy_supply"] = [
                    {"fuel": fuel, "value": val} for fuel, val in sorted(supply[year][econ].items())
                ]
            if year in elec and econ in elec[year]:
                sectors["18_electricity_output_in_gwh"] = [
                    {"fuel": fuel, "value": val} for fuel, val in sorted(elec[year][econ].items())
                ]
            if sectors:
                sector_map[econ] = sectors
        by_year[year] = sector_map
    return by_year


def generate_ei_assets(
    workbook: Path,
    output_json: Path,
    supply_sheet: str = "TES by fuel",
    elec_sheet: str = "Elec generation by fuel",
    scenario: str = "historical",
) -> int:
    """
    Extract EI workbook data into the app JSON structure (currently 2023 & 2024 only).
    """
    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")

    supply_raw = _read_by_fuel_sheet(
        workbook,
        sheet=supply_sheet,
        fuel_map=SUPPLY_FUEL_MAP,
        unit_to_pj=1000.0,  # EJ -> PJ
        year_suffixes=YEAR_SUFFIXES,
    )
    elec_raw = _read_by_fuel_sheet(
        workbook,
        sheet=elec_sheet,
        fuel_map=ELEC_FUEL_MAP,
        unit_to_pj=3.6,  # TWh -> PJ
        year_suffixes=YEAR_SUFFIXES,
    )

    # Extract names from the sentinel bucket
    names: Dict[str, str] = {}
    for source in (supply_raw, elec_raw):
        meta = source.pop(-1, {})
        for econ_code, meta_entry in meta.items():
            names.setdefault(econ_code, meta_entry.get("name", econ_code))

    sectors_by_year = _merge_sector_data(supply_raw, elec_raw)
    years = sorted(sectors_by_year.keys())

    datasets: Dict[str, Dict] = {}
    profile_counts: List[int] = []
    for year in years:
        profiles: List[Dict] = []
        for econ_code, sectors in sorted(sectors_by_year[year].items()):
            profile = {
                "economy": econ_code,
                "name": names.get(econ_code, econ_code),
                "source": "EI",
                "sectors": sectors,
            }
            profile = prep._attach_metrics(profile, exports_negative=False)
            prep._validate_metrics(profile)
            profiles.append(profile)
        datasets[str(year)] = {"year": year, "scenario": scenario, "profiles": profiles}
        profile_counts.append(len(profiles))

    out_obj = {
        "years": years,
        "defaultYear": max(years),
        "scenario": scenario,
        "datasets": datasets,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(out_obj, indent=2))
    prep._write_group_shards(out_obj, output_json)
    print(f"[INFO] Wrote EI profiles for years {years} to {output_json}")
    return sum(profile_counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create EI energy assets (PJ) from the EI workbook.")
    parser.add_argument(
        "--input",
        default="EI-Stats-Review-ALL-data.xlsx",
        help="Path to EI-Stats-Review-ALL-data.xlsx",
    )
    parser.add_argument(
        "--output-json",
        default="public/data/energy-profiles-ei.json",
        help="Where to write the EI JSON dataset.",
    )
    args = parser.parse_args()

    generate_ei_assets(Path(args.input), Path(args.output_json))


if __name__ == "__main__":
    main()
