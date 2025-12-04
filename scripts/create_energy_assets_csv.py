#!/usr/bin/env python3
"""
Create a multi-year energy-profiles.json from a large CSV without exposing the source file.

Example:
python scripts/create_energy_assets_csv.py ^
  --input ./merged_file_energy_ALL_20250814.csv ^
  --output-json ./public/data/energy-profiles.json ^
  --scenario reference

Notes:
- By default, extracts every 5th year available in the CSV (e.g., 2000, 2005, 2010, …) and uses 2020 as the default year if present.
- If year <= 2022, rows are filtered with subtotal_layout == False (when the column exists).
- If year > 2022, rows are filtered with subtotal_results == False (when the column exists).
- Required columns in the CSV:
  * economy (or set --economy-column)
  * sectors (or set --sector-column)
  * scenarios (or set --scenario-column)
  * fuels (or set --fuel-column)
  * numeric columns named after years (e.g., 2020, 2025, 2030)
  * optional human-readable name column (set --label-column, defaults to economy)
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable

import pandas as pd

DEFAULT_SECTORS = [
  "07_total_primary_energy_supply",
  "12_total_final_consumption",
  "09_total_transformation_sector",
]
# Additional sectors used for stats but not charted
STATS_ONLY_SECTORS = [
  "18_electricity_output_in_gwh",
  "02_imports",
  "03_exports",
  "net_imports",
]
TFC_SECTOR_PARTS = [
  "14_industry_sector",
  "15_transport_sector",
  "16_other_sector",
  "17_nonenergy_use",
]

# Enforce inclusion and naming for the specified economies.
ECONOMY_NAME_OVERRIDES = {
  "01_AUS": "Australia",
  "02_BD": "Brunei Darussalam",
  "03_CDA": "Canada",
  "04_CHL": "Chile",
  "05_PRC": "China",
  "06_HKC": "Hong Kong",
  "07_INA": "Indonesia",
  "08_JPN": "Japan",
  "09_ROK": "Korea",
  "10_MAS": "Malaysia",
  "11_MEX": "Mexico",
  "12_NZ": "New Zealand",
  "13_PNG": "Papua New Guinea",
  "14_PE": "Peru",
  "15_PHL": "Philippines",
  "16_RUS": "Russia",
  "17_SGP": "Singapore",
  "18_CT": "Chinese Taipei",
  "19_THA": "Thailand",
  "20_USA": "USA",
  "21_VN": "Viet Nam",
}
ECONOMY_ALLOWLIST = set(ECONOMY_NAME_OVERRIDES.keys())

FUEL_GROUP_MAP = {
  "01_coal": "coal",
  "02_coal_products": "coal",
  "03_peat": "coal",
  "04_peat_products": "coal",
  "05_oil_shale_and_oil_sands": "coal",
  "06_crude_oil_and_ngl": "oil",
  "07_petroleum_products": "oil",
  "08_gas": "gas",
  "09_nuclear": "renewables_and_others",
  "10_hydro": "renewables_and_others",
  "11_geothermal": "renewables_and_others",
  "12_solar": "renewables_and_others",
  "13_tide_wave_ocean": "renewables_and_others",
  "14_wind": "renewables_and_others",
  "15_solid_biomass": "renewables_and_others",
  "16_others": "renewables_and_others",
  "17_electricity": "electricity",
  "17_x_green_electricity": "renewables_and_others",
  "18_heat": "renewables_and_others",
}

def fuel_group(fuel_code: str) -> str:
  fuel_code = fuel_code.strip()
  return FUEL_GROUP_MAP.get(fuel_code, "other")


def detect_years(header: pd.DataFrame, explicit_years: Iterable[int] | None) -> list[int]:
  if explicit_years:
    return sorted({int(y) for y in explicit_years})

  year_cols: list[int] = []
  for col in header.columns:
    col_str = str(col)
    if col_str.isdigit():
      year_cols.append(int(col_str))
  year_cols = sorted(set(year_cols))
  # Default: every 5th year
  return [y for y in year_cols if y % 5 == 0]


def build_profiles(
  path: Path,
  years: Iterable[int],
  default_year: int,
  scenario: str,
  sectors: Iterable[str],
  economy_col: str,
  sector_col: str,
  sub1sector_col: str,
  scenario_col: str,
  fuel_col: str,
  label_col: str,
  chunksize: int,
) -> Dict:
  header = pd.read_csv(path, nrows=0)
  available_years = detect_years(header, years)
  if not available_years:
    raise ValueError("No year columns found to process.")

  label_available = bool(label_col) and label_col in header.columns
  if label_col and not label_available:
    print(
      f"Warning: label column '{label_col}' not found in CSV; using economy code for names."
    )

  normalized_scenario = scenario.lower().strip()
  normalized_sectors = {s.lower().strip() for s in sectors}
  normalized_filter_sectors = normalized_sectors.union(
    {s.lower() for s in STATS_ONLY_SECTORS}
  ).union({s.lower() for s in TFC_SECTOR_PARTS})

  datasets: Dict[str, Dict] = {}
  for year in available_years:
    year_col = str(year)
    needed_columns = {
      economy_col,
      sector_col,
      scenario_col,
      fuel_col,
      year_col,
    }
    needs_subtotal_results = year > 2022
    needs_subtotal_layout = year <= 2022
    if needs_subtotal_results:
      needed_columns.add("subtotal_results")
    if needs_subtotal_layout:
      needed_columns.add("subtotal_layout")
    if label_available:
      needed_columns.add(label_col)
    if sub1sector_col:
      needed_columns.add(sub1sector_col)

    fuel_totals: DefaultDict[str, DefaultDict[str, DefaultDict[str, float]]] = defaultdict(
      lambda: defaultdict(lambda: defaultdict(float))
    )
    tfc_totals: DefaultDict[str, DefaultDict[str, float]] = defaultdict(
      lambda: defaultdict(float)
    )
    profiles: Dict[str, Dict] = {}
    seen_economies = set()

    for chunk in pd.read_csv(
      path,
      usecols=list(needed_columns),
      chunksize=chunksize,
    ):
      chunk[economy_col] = chunk[economy_col].astype(str).str.strip()
      chunk[sector_col] = chunk[sector_col].astype(str).str.strip()
      if sub1sector_col and sub1sector_col in chunk.columns:
        chunk[sub1sector_col] = chunk[sub1sector_col].astype(str).str.strip()
      chunk[scenario_col] = chunk[scenario_col].astype(str).str.strip().str.lower()
      chunk[year_col] = pd.to_numeric(chunk[year_col], errors="coerce")
      if label_available:
        chunk[label_col] = chunk[label_col].astype(str).str.strip()

      filtered = chunk[
        (chunk[scenario_col] == normalized_scenario)
        & (chunk[sector_col].str.lower().isin(normalized_filter_sectors))
        & (chunk[economy_col].isin(ECONOMY_ALLOWLIST))
      ].dropna(subset=[year_col])

      if needs_subtotal_results and "subtotal_results" in filtered.columns:
        filtered = filtered[filtered["subtotal_results"] == False]  # noqa: E712
      if needs_subtotal_layout and "subtotal_layout" in filtered.columns:
        filtered = filtered[filtered["subtotal_layout"] == False]  # noqa: E712

      if filtered.empty:
        continue

      filtered["fuel_group"] = filtered[fuel_col].apply(fuel_group)

      group_cols = [economy_col, sector_col, "fuel_group"]
      if sub1sector_col and sub1sector_col in filtered.columns:
        group_cols.append(sub1sector_col)
      agg_dict = {year_col: "sum"}
      if label_available:
        agg_dict[label_col] = "first"

      grouped = filtered.groupby(group_cols, as_index=False).agg(agg_dict)

      for _, row in grouped.iterrows():
        economy = str(row[economy_col]).strip()
        sector = str(row[sector_col]).strip()
        sector_lower = sector.lower()
        fuel = str(row["fuel_group"]).strip()
        value = float(row[year_col])
        if sector_lower == "18_electricity_output_in_gwh":
          value = value * 0.0036

        seen_economies.add(economy)
        name_value = (
          ECONOMY_NAME_OVERRIDES.get(economy)
          or (
            str(row[label_col]).strip()
            if label_available and label_col in row
            else None
          )
          or economy
        )
        profile = profiles.setdefault(
          economy, {"economy": economy, "name": name_value, "sectors": {}}
        )
        if profile.get("name") != name_value:
          profile["name"] = name_value

        if sector_lower in TFC_SECTOR_PARTS:
          tfc_key = None
          if sector_lower == "14_industry_sector":
            tfc_key = "industry"
          elif sector_lower == "15_transport_sector":
            tfc_key = "transport"
          elif sector_lower == "17_nonenergy_use":
            tfc_key = "non_energy_use"
          elif sector_lower == "16_other_sector":
            sub1 = (
              str(row[sub1sector_col]).strip().lower()
              if sub1sector_col and sub1sector_col in row
              else ""
            )
            if sub1 in {"16_01_buildings"}:
              tfc_key = "buildings"
            elif sub1 in {
              "16_02_agriculture_and_fishing",
              "16_05_nonspecified_others",
            }:
              tfc_key = "others"
          if tfc_key:
            tfc_totals[economy][tfc_key] += value

        fuel_totals[economy][sector][fuel] += value

    # Ensure all allowlisted economies exist, even if empty in source.
    for code, readable in ECONOMY_NAME_OVERRIDES.items():
      profiles.setdefault(code, {"economy": code, "name": readable, "sectors": {}})

    for economy, sectors_map in fuel_totals.items():
      profile = profiles.setdefault(
        economy, {"economy": economy, "name": economy, "sectors": {}}
      )
      sector_payload: Dict[str, list] = {}
      for sector, fuels in sectors_map.items():
        sector_payload[sector] = [
          {"fuel": fuel, "value": float(value)} for fuel, value in fuels.items()
        ]

      if tfc_totals.get(economy):
        sector_payload["12_total_final_consumption"] = [
          {"fuel": key, "value": float(val)} for key, val in tfc_totals[economy].items()
        ]

      imports = sector_payload.get("02_imports", [])
      exports = sector_payload.get("03_exports", [])
      if imports or exports:
        fuel_map: Dict[str, float] = {}
        for item in imports:
          fuel_map[item["fuel"]] = fuel_map.get(item["fuel"], 0.0) + float(
            item["value"]
          )
        for item in exports:
          fuel_map[item["fuel"]] = fuel_map.get(item["fuel"], 0.0) - abs(
            float(item["value"])
          )
        sector_payload["net_imports"] = [
          {"fuel": fuel, "value": val} for fuel, val in fuel_map.items()
        ]

      profile["sectors"] = sector_payload

    datasets[str(year)] = {
      "profiles": list(profiles.values()),
      "sectors": list(
        {s for s in sectors}.union(
          {"18_electricity_output_in_gwh", "02_imports", "03_exports", "net_imports"}
        )
      ),
      "year": year,
      "scenario": scenario,
    }

  chosen_default = default_year if str(default_year) in datasets else available_years[0]

  return {
    "years": available_years,
    "defaultYear": chosen_default,
    "scenario": scenario,
    "datasets": datasets,
  }


def main() -> None:
  parser = argparse.ArgumentParser(description="Create energy assets from CSV.")
  parser.add_argument("--input", required=True, help="Path to the CSV file.")
  parser.add_argument(
    "--output-json",
    default="public/data/energy-profiles.json",
    help="Where to write the JSON dataset.",
  )
  parser.add_argument(
    "--year",
    type=int,
    help="(Deprecated) Single year to use; prefer --years.",
  )
  parser.add_argument(
    "--years",
    nargs="+",
    type=int,
    help="List of years to include (default: every 5th year found in CSV).",
  )
  parser.add_argument(
    "--default-year",
    type=int,
    default=2020,
    help="Which year to show by default (must exist in the data; falls back to first available).",
  )
  parser.add_argument(
    "--scenario",
    default="reference",
    help="Scenario to filter on (default: reference).",
  )
  parser.add_argument(
    "--sectors",
    nargs="+",
    default=DEFAULT_SECTORS,
    help="Sectors to keep (space separated).",
  )
  parser.add_argument(
    "--economy-column",
    default="economy",
    help="Column name for economy codes.",
  )
  parser.add_argument(
    "--sector-column",
    default="sectors",
    help="Column name for sector keys.",
  )
  parser.add_argument(
    "--sub1sector-column",
    default="sub1sectors",
    help="Column name for sub1 sector keys (used to split TFC others).",
  )
  parser.add_argument(
    "--scenario-column",
    default="scenarios",
    help="Column name for scenario values.",
  )
  parser.add_argument(
    "--fuel-column",
    default="fuels",
    help="Column name for fuel values.",
  )
  parser.add_argument(
    "--label-column",
    default="economy_name",
    help="Optional column for readable names (defaults to economy if missing).",
  )
  parser.add_argument(
    "--chunksize",
    type=int,
    default=200_000,
    help="CSV chunksize for memory-friendly processing.",
  )

  args = parser.parse_args()

  input_path = Path(args.input)
  output_path = Path(args.output_json)

  years_to_use = []
  if args.years:
    years_to_use.extend(args.years)
  if args.year:
    years_to_use.append(args.year)

  dataset = build_profiles(
    path=input_path,
    years=years_to_use,
    default_year=args.default_year,
    scenario=args.scenario,
    sectors=args.sectors,
    economy_col=args.economy_column,
    sector_col=args.sector_column,
    sub1sector_col=args.sub1sector_column,
    scenario_col=args.scenario_column,
    fuel_col=args.fuel_column,
    label_col=args.label_column,
    chunksize=args.chunksize,
  )

  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(json.dumps(dataset, indent=2))
  default_year = dataset.get("defaultYear")
  profiles_default_year = dataset["datasets"].get(str(default_year), {}).get(
    "profiles", []
  )
  print(
    f"Wrote {len(profiles_default_year)} profiles "
    f"for default year {default_year} to {output_path}. "
    f"Years available: {', '.join(str(y) for y in dataset.get('years', []))}."
  )


if __name__ == "__main__":
  main()
