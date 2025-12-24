#!/usr/bin/env python3
#%%
"""
Turn an energy balances Excel file into ready-to-use assets for the app.

Example:
python scripts/create_energy_assets.py ^
  --input ./data/australia_balances.xlsx ^
  --output-json ./public/data/energy-profiles-apec.json ^
  --charts-dir ./public/energy-graphs ^
  --year 2020 --scenario reference

Required columns in the Excel sheet:
- economy (e.g. 01_AUS)
- sectors (e.g. 07_total_primary_energy_supply)
- scenarios (e.g. reference)
- fuels (e.g. coal)
- a numeric column with the selected year (e.g. 2020)

Dependencies: pandas, matplotlib, openpyxl.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import matplotlib.pyplot as plt
import pandas as pd
import math
from mappings import (
    CHART_FUELS,
    ELEC_PRODUCTION_LABELS,
    PRIMARY_PRODUCTION_LABELS_KEEP,
    PRODUCTION_DROP_LABELS,
    PRODUCTION_FUEL_KEEP,
    UN_FUEL_MAP,
    UN_MAPPED_FUELS,
    is_production_dropped,
    is_production_kept,
    map_un_fuel,
    write_chart_meta,
)

APEC_NAME_MAP = {
    "01_AUS": "Australia",
    "02_BD": "Brunei Darussalam",
    "03_CDA": "Canada",
    "04_CHL": "Chile",
    "05_PRC": "China",
    "06_HKC": "Hong Kong, China",
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
    "20_USA": "United States",
    "21_VN": "Viet Nam",
}


def _map_apec_fuel(fuel: str) -> Optional[str]:
    """
    Collapse APEC fuel codes to chart fuels.
    """
    f = fuel.lower().strip()
    if f.startswith("01_") or f.startswith("02_") or f.startswith("03_") or f.startswith("04_"):
        return "coal"
    if f.startswith("05_") or f.startswith("06_") or f.startswith("07_"):
        return "oil"
    if f.startswith("08_"):
        return "gas"
    if f.startswith("17_"):
        return "electricity"
    if f.startswith("09_") or f.startswith("10_") or f.startswith("11_") or f.startswith("12_") or f.startswith("13_") or f.startswith("14_") or f.startswith("15_") or f.startswith("16_") or f.startswith("18_"):
        return "renewables_and_others"
    return None


def _map_apec_elec_fuel(fuel: str) -> Optional[str]:
    """
    Detailed mapping for APEC electricity generation fuels.
    """
    f = fuel.lower().strip()
    # Coal family
    if f.startswith("01_") or f.startswith("02_") or f.startswith("03_") or f.startswith("04_"):
        return "coal"
    # Oil family
    if f.startswith("05_") or f.startswith("06_") or f.startswith("07_"):
        return "oil"
    # Gas
    if f.startswith("08_"):
        return "gas"
    # Nuclear
    if f.startswith("09_"):
        return "nuclear"
    # Hydro / geothermal
    if f.startswith("10_"):
        return "hydro"
    if f.startswith("11_"):
        return "geothermal"
    # Variable renewables
    if f.startswith("12_") or f.startswith("13_") or f.startswith("14_"):
        return "wind_solar"
    # Biomass / other renewables
    if f.startswith("15_") or f.startswith("16_"):
        return "renewables_and_others"
    # Ignore aggregates and non-generation fuel rows for elec output
    return None


def _sector_totals(
    sectors: Dict[str, List[Dict[str, float]]], exports_negative: bool
) -> Dict[str, float]:
    def sum_sector(key: str) -> float:
        return sum(float(f.get("value", 0) or 0) for f in sectors.get(key, []))

    imports = sum_sector("02_imports")
    exports = sum_sector("03_exports")
    # Prefer explicit imports/exports when present; otherwise, fall back to net_imports sector
    if imports != 0 or exports != 0:
        net_imports = imports + (exports if exports_negative else -exports)
    else:
        net_imports = sum_sector("net_imports")

    # Prefer production if present, else fall back to TPES
    production = sum_sector("01_production")
    tpes = production if production else sum_sector("07_total_primary_energy_supply")
    tfc = sum_sector("12_total_final_consumption")
    elec_gen = sum_sector("18_electricity_output_in_gwh")

    return {
        "tpes": tpes,
        "tfc": tfc,
        "elec_gen": elec_gen,
        "net_imports": net_imports,
    }


def _net_imports_by_fuel(
    sectors: Dict[str, List[Dict[str, float]]], exports_negative: bool
) -> List[Dict[str, float]]:
    fuel_map: Dict[str, float] = {}
    imports = sectors.get("02_imports", [])
    exports = sectors.get("03_exports", [])

    if imports or exports:
        for item in imports:
            fuel = item.get("fuel")
            if fuel:
                fuel_map[fuel] = fuel_map.get(fuel, 0.0) + float(item.get("value", 0) or 0)
        for item in exports:
            fuel = item.get("fuel")
            if fuel:
                adj = float(item.get("value", 0) or 0)
                fuel_map[fuel] = fuel_map.get(fuel, 0.0) + (adj if exports_negative else -adj)
    elif "net_imports" in sectors:
        for item in sectors.get("net_imports", []):
            fuel = item.get("fuel")
            if fuel:
                fuel_map[fuel] = fuel_map.get(fuel, 0.0) + float(item.get("value", 0) or 0)

    return [{"fuel": k, "value": v} for k, v in sorted(fuel_map.items())]


def _sector_stats(sectors: Dict[str, List[Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    for key, fuels in sectors.items():
        if not fuels:
            continue
        vals = [float(f.get("value", 0) or 0) for f in fuels]
        stats[key] = {"max": max(vals), "min": min(vals)}
    return stats


def _aggregate_fuels(
    fuels: List[Dict[str, float]],
    keep: set[str] = CHART_FUELS,
    mapper: Optional[callable] = None,
) -> List[Dict[str, float]]:
    agg: Dict[str, float] = {}
    for f in fuels:
        fuel_raw = f.get("fuel")
        fuel = mapper(fuel_raw) if mapper else fuel_raw
        if fuel not in keep:
            continue
        agg[fuel] = agg.get(fuel, 0.0) + float(f.get("value", 0) or 0)
    return [{"fuel": k, "value": v} for k, v in sorted(agg.items())]


def _drop_tiny_contributors(
    fuels: List[Dict[str, float]], threshold: float = 0.01
) -> List[Dict[str, float]]:
    """
    Remove fuels that contribute less than a threshold fraction of the
    largest absolute value in the sector. Keeps all entries when max is 0.
    """
    if not fuels:
        return fuels
    max_abs = max(abs(float(f.get("value", 0) or 0)) for f in fuels)
    if max_abs <= 0:
        return fuels
    cutoff = max_abs * threshold
    filtered = [f for f in fuels if abs(float(f.get("value", 0) or 0)) >= cutoff]
    return filtered


def _write_group_shards(out_obj: Dict, output_json: Path, group_size: int = 50) -> None:
    """
    Split datasets into year-first, economy-group shards and write an index:
    - index: { years, defaultYear, scenario, year_groups: {year: [{id,file,economies}]} }
    - shards: <stem>-<year>-gN.json containing only that year's subset of economies.
    """
    datasets = out_obj.get("datasets", {})
    years = out_obj.get("years", [])
    default_year = out_obj.get("defaultYear")
    scenario = out_obj.get("scenario")

    index_path = output_json.with_name(f"{output_json.stem}.index.json")
    year_groups: Dict[str, List[Dict[str, object]]] = {}

    # Clean up any old shard files for this stem to avoid stale data
    shard_glob = f"{output_json.stem}-*-g*.json"
    for old in output_json.parent.glob(shard_glob):
        try:
            old.unlink()
        except OSError:
            pass

    for year_str, data in datasets.items():
        profiles = data.get("profiles", [])
        economies = sorted({p.get("economy", "") for p in profiles})
        groups: List[Dict[str, object]] = []
        for idx in range(0, len(economies), group_size):
            econ_slice = economies[idx : idx + group_size]
            group_id = f"g{idx // group_size}"
            filtered = [p for p in profiles if p.get("economy") in econ_slice]
            shard = {
                "year": data.get("year"),
                "scenario": data.get("scenario", scenario),
                "profiles": filtered,
            }
            shard_path = output_json.with_name(
                f"{output_json.stem}-{year_str}-{group_id}{output_json.suffix}"
            )
            shard_path.write_text(json.dumps(shard, indent=2))
            groups.append(
                {"id": group_id, "file": shard_path.name, "economies": econ_slice}
            )
        year_groups[year_str] = groups

    index_payload = {
        "years": years,
        "defaultYear": default_year,
        "scenario": scenario,
        "year_groups": year_groups,
    }
    index_path.write_text(json.dumps(index_payload, indent=2))


def _prune_sectors(
    sectors: Dict[str, List[Dict[str, float]]],
    aggregate_tfc: bool = True,
    fuel_mapper: Optional[callable] = None,
) -> Dict[str, List[Dict[str, float]]]:
    # Keep only the sectors we chart, and aggregate to simple shapes:
    # - TPES: by fuel
    # - TFC: by fuel (aggregate from end-use sectors)
    # - End-use sectors by fuel: industry, transport, buildings, other, non-energy
    # - Elec gen: by fuel
    # - Net imports: by fuel
    pruned: Dict[str, List[Dict[str, float]]] = {}

    if "01_production" in sectors:
        pruned["01_production"] = _drop_tiny_contributors(
            _aggregate_fuels(sectors["01_production"], mapper=fuel_mapper, keep=PRODUCTION_FUEL_KEEP)
        )
    elif "07_total_primary_energy_supply" in sectors:
        pruned["07_total_primary_energy_supply"] = _drop_tiny_contributors(
            _aggregate_fuels(
                sectors["07_total_primary_energy_supply"], mapper=fuel_mapper, keep=PRODUCTION_FUEL_KEEP
            )
        )

    # Keep end-use sectors if present
    for key in [
        "14_industry_sector",
        "15_transport_sector",
        "16_buildings_sector",
        "16_other_sector",
        "17_nonenergy_use",
    ]:
        if key in sectors:
            pruned[key] = _drop_tiny_contributors(
                _aggregate_fuels(sectors[key], mapper=fuel_mapper)
            )

    # Derive TFC by sector (not by fuel) from end-use sectors
    if aggregate_tfc:
        sector_map = {
            "14_industry_sector": "industry",
            "15_transport_sector": "transport",
            "16_buildings_sector": "buildings",
            "16_other_sector": "others",
            "17_nonenergy_use": "non_energy_use",
        }
        tfc_entries: List[Dict[str, float]] = []
        for key, label in sector_map.items():
            if key in pruned:
                total_val = sum(float(f.get("value", 0) or 0) for f in pruned[key])
                tfc_entries.append({"fuel": label, "value": total_val})
        pruned["12_total_final_consumption"] = _drop_tiny_contributors(tfc_entries)

    if "18_electricity_output_in_gwh" in sectors:
        pruned["18_electricity_output_in_gwh"] = _drop_tiny_contributors(
            _aggregate_fuels(
                sectors["18_electricity_output_in_gwh"],
                mapper=_map_apec_elec_fuel if fuel_mapper else fuel_mapper,
            )
        )

    if "net_imports" in sectors:
        net_fuels = sectors["net_imports"]
        pruned["net_imports"] = _drop_tiny_contributors(
            _aggregate_fuels(net_fuels, mapper=fuel_mapper)
        )

    return pruned


def _map_apec_sector(sector: str, sub2sector: Optional[str]) -> str:
    if sector == "16_other_sector" and sub2sector:
        lbl = sub2sector.lower()
        if "commercial" in lbl or "public" in lbl:
            return "16_buildings_sector"
        if "residential" in lbl:
            return "16_buildings_sector"
    return sector


def _attach_metrics(profile: Dict, exports_negative: bool) -> Dict:
    sectors = profile.get("sectors", {})
    profile["metrics"] = {
        **_sector_totals(sectors, exports_negative),
        "net_imports_by_fuel": _net_imports_by_fuel(sectors, exports_negative),
    }
    return profile


def _validate_metrics(profile: Dict) -> None:
    """
    Sanity check that metrics match sector sums; logs warnings if mismatched.
    """
    name = profile.get("economy", "unknown")
    sectors = profile.get("sectors", {})
    metrics = profile.get("metrics", {})

    def sum_sector(key: str) -> float:
        return sum(float(f.get("value", 0) or 0) for f in sectors.get(key, []))

    checks = {
        "tpes": (
            "01_production"
            if "01_production" in sectors
            else "07_total_primary_energy_supply",
            metrics.get("tpes"),
        ),
        "tfc": ("12_total_final_consumption", metrics.get("tfc")),
        "elec_gen": ("18_electricity_output_in_gwh", metrics.get("elec_gen")),
        "net_imports": ("net_imports", metrics.get("net_imports")),
    }
    for label, (sector_key, metric_val) in checks.items():
        if metric_val is None:
            continue
        sector_sum = sum_sector(sector_key)
        if abs(sector_sum - metric_val) > max(1.0, 0.01 * abs(metric_val)):
            print(f"[WARN] Metrics mismatch {name} {label}: metric={metric_val} sector_sum={sector_sum}")


DEFAULT_SECTORS = [
    "01_production",
    "07_total_primary_energy_supply",
    "12_total_final_consumption",
    "14_industry_sector",
    "15_transport_sector",
    "16_buildings_sector",
    "16_other_sector",
    "17_nonenergy_use",
    "18_electricity_output_in_gwh",
    "02_imports",
    "03_exports",
    "09_total_transformation_sector",
]
UN_SECTORS = [
    "01_production",
    "02_imports",
    "03_exports",
    "07_total_primary_energy_supply",
    "09_total_transformation_sector",
    "12_total_final_consumption",
    "14_industry_sector",
    "15_transport_sector",
    "16_buildings_sector",
    "16_other_sector",
    "17_nonenergy_use",
    "18_electricity_output_in_gwh",
    "net_imports",
]
DEFAULT_SOURCE = "APEC"


def build_profile(
    df: pd.DataFrame,
    economy: str,
    sectors: Iterable[str],
    year: int,
    label_column: str,
    source: str = DEFAULT_SOURCE,
) -> Dict:
    # Choose best available label
    label_col = (
        label_column
        if label_column in df.columns and label_column != "economy"
        else None
    )
    if not label_col and "economy_name" in df.columns:
        label_col = "economy_name"
    name_val = (
        str(df[df["economy"] == economy][label_col].iloc[0])
        if label_col
        else APEC_NAME_MAP.get(economy, economy)
    )
    profile: Dict = {
        "economy": economy,
        "name": name_val,
        "source": source,
        "sectors": {},
    }

    for sector in sectors:
        filtered = df[
            (df["economy"] == economy)
            & (df["sectors"] == sector)
            & (~df[year].isna())
        ]
        by_fuel = filtered.groupby("fuels")[year].sum().reset_index()
        profile["sectors"][sector] = [
            {
                "fuel": row["fuels"],
                "value": float(row[year])
                * (0.0036 if sector == "18_electricity_output_in_gwh" else 1.0),
            }
            for _, row in by_fuel.iterrows()
        ]

    return profile


def render_charts(
    profile: Dict, sectors: List[str], year: int, charts_dir: Path
) -> str:
    charts_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(sectors), figsize=(5 * len(sectors), 4))
    if len(sectors) == 1:
        axes = [axes]

    for ax, sector in zip(axes, sectors):
        sector_data = profile["sectors"].get(sector, [])
        fuels = [item["fuel"] for item in sector_data]
        values = [item["value"] for item in sector_data]

        ax.bar(fuels, values)
        ax.set_title(sector)
        ax.set_xticklabels(fuels, rotation=90)
        ax.set_ylabel("PJ")
        ax.set_xlabel(f"Values for {year}")

    plt.tight_layout()
    filename = f"{profile['economy']}.png"
    fig.savefig(charts_dir / filename, bbox_inches="tight")
    plt.close(fig)
    return filename


def generate_apec_assets_csv_multi(
    input_path: Path,
    output_json: Path,
    years: List[int],
    default_year: int,
    scenario: str,
    label_column: str = "economy",
    chunksize: int = 50000,
) -> int:
    """
    Chunked CSV -> multi-year JSON generation for APEC data.
    """
    year_cols = [str(y) for y in years]
    needed_columns = {"economy", "sectors", "scenarios", "fuels", *year_cols}
    sub2_present = False
    if label_column:
        needed_columns.add(label_column)

    totals: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {
        str(y): {} for y in years
    }
    names: Dict[str, str] = {}
    norm_scenario = scenario.strip().lower()

    for chunk in pd.read_csv(input_path, chunksize=chunksize):
        # detect sub2sectors column
        if "sub2sectors" in chunk.columns:
            sub2_present = True
            needed = set(needed_columns) | {"sub2sectors"}
        else:
            needed = needed_columns
        missing = [c for c in needed if c not in chunk.columns]
        if missing:
            continue
        chunk = chunk[list(needed)]
        chunk["economy"] = chunk["economy"].astype(str).str.strip()
        chunk["sectors"] = chunk["sectors"].astype(str).str.strip()
        chunk["scenarios"] = chunk["scenarios"].astype(str).str.strip().str.lower()
        chunk["fuels"] = chunk["fuels"].astype(str).str.strip()
        if "sub2sectors" in chunk.columns:
            chunk["sub2sectors"] = chunk["sub2sectors"].astype(str).str.strip()
        label_col = None
        if label_column in chunk.columns and label_column != "economy":
            label_col = label_column
        elif "economy_name" in chunk.columns:
            label_col = "economy_name"
        if label_col:
            chunk[label_col] = chunk[label_col].astype(str).str.strip()

        chunk = chunk[chunk["scenarios"] == norm_scenario]
        if chunk.empty:
            continue

        if label_col:
            names.update(chunk.groupby("economy")[label_col].first().to_dict())
        else:
            # fallback to static map
            names.update({econ: APEC_NAME_MAP.get(econ, econ) for econ in chunk["economy"].unique()})

        for y in years:
            col = str(y)
            if col not in chunk.columns:
                continue
            sub = chunk.dropna(subset=[col])
            if sub.empty:
                continue
            if "sub2sectors" in sub.columns:
                sub["sector_mapped"] = sub.apply(
                    lambda r: _map_apec_sector(r["sectors"], r.get("sub2sectors")),
                    axis=1,
                )
            else:
                sub["sector_mapped"] = sub["sectors"]

            grouped = (
                sub.groupby(["economy", "sector_mapped", "fuels"])[col]
                .sum(min_count=1)
                .reset_index()
            )
            for _, row in grouped.iterrows():
                econ = row["economy"]
                sector = row["sector_mapped"]
                fuel = row["fuels"]
                val = float(row[col])
                if sector == "18_electricity_output_in_gwh":
                    val *= 0.0036  # convert GWh to PJ
                econ_entry = totals[col].setdefault(econ, {})
                fuel_map = econ_entry.setdefault(sector, {})
                fuel_map[fuel] = fuel_map.get(fuel, 0.0) + val

    datasets: Dict[str, Dict] = {}
    profile_counts: List[int] = []
    for y in sorted(years):
        y_str = str(y)
        econ_totals = totals.get(y_str, {})
        profiles: List[Dict] = []
        for econ_code in sorted(econ_totals.keys()):
            sector_data = {}
            for sector, fuel_map in econ_totals[econ_code].items():
                sector_data[sector] = [
                    {"fuel": fuel, "value": float(val)}
                    for fuel, val in sorted(fuel_map.items())
                ]
            # Compute net imports by fuel if imports/exports present
            imports = sector_data.get("02_imports", [])
            exports = sector_data.get("03_exports", [])
            if imports or exports:
                net_map: Dict[str, float] = {}
                for item in imports:
                    net_map[item["fuel"]] = net_map.get(item["fuel"], 0.0) + item["value"]
                for item in exports:
                    net_map[item["fuel"]] = net_map.get(item["fuel"], 0.0) + item["value"]
                sector_data["net_imports"] = [
                    {"fuel": f, "value": v} for f, v in sorted(net_map.items())
                ]
            sector_data = _prune_sectors(
                sector_data, aggregate_tfc=True, fuel_mapper=_map_apec_fuel
            )
            profile = _attach_metrics(
                {
                    "economy": econ_code,
                    "name": names.get(econ_code, econ_code),
                    "source": "APEC",
                    "sectors": sector_data,
                },
                exports_negative=False,
            )
            _validate_metrics(profile)
            profiles.append(profile)
        datasets[y_str] = {
            "year": y,
            "scenario": scenario,
            "profiles": profiles,
        }
        profile_counts.append(len(profiles))

    out_obj = {
        "years": sorted(years),
        "defaultYear": default_year if default_year in years else years[0],
        "scenario": scenario,
        "datasets": datasets,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(out_obj, indent=2))
    print(f"[INFO] Wrote APEC CSV profiles for years {years} to {output_json}")
    _write_group_shards(out_obj, output_json)
    return sum(profile_counts)


def generate_apec_assets(
    input_path: Path,
    output_json: Path,
    charts_dir: Path,
    year: int,
    scenario: str,
    sectors: List[str],
    label_column: str,
    skip_charts: bool,
    source: str = DEFAULT_SOURCE,
) -> int:
    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)
    filtered = df[(df["scenarios"] == scenario) & (df["sectors"].isin(sectors))]
    #set the year col names to ints
    filtered.columns = [int(col) if str(col).isdigit() else col for col in filtered.columns]
    
    economies = sorted(filtered["economy"].unique())
    profiles: List[Dict] = []

    for economy in economies:
        profile = build_profile(
            filtered,
            economy,
            sectors,
            year,
            label_column,
            source=source,
        )
        if not skip_charts:
            profile["chartImage"] = render_charts(
                profile, sectors, year, charts_dir
            )
        # Compute net imports if imports/exports are present
        imports = profile["sectors"].get("02_imports", [])
        exports = profile["sectors"].get("03_exports", [])
        if imports or exports:
            net_map: Dict[str, float] = {}
            for item in imports:
                net_map[item["fuel"]] = net_map.get(item["fuel"], 0.0) + item["value"]
            for item in exports:
                net_map[item["fuel"]] = net_map.get(item["fuel"], 0.0) + item["value"]
            profile["sectors"]["net_imports"] = [
                {"fuel": f, "value": v} for f, v in sorted(net_map.items())
            ]
        profile["sectors"] = _prune_sectors(
            profile["sectors"], aggregate_tfc=True, fuel_mapper=_map_apec_fuel
        )
        profile = _attach_metrics(profile, exports_negative=False)
        _validate_metrics(profile)
        profiles.append(profile)

    dataset = {
        "year": year,
        "scenario": scenario,
        "sectors": sectors,
        "profiles": profiles,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(dataset, indent=2))
    print(f"[INFO] Wrote {len(profiles)} APEC profiles to {output_json}")
    _write_group_shards(dataset, output_json)
    return len(profiles)


def _map_economy_code(ref_area: str, label: str) -> tuple[str, str]:
    """
    Map UN REF_AREA/label to economy code and display name.
    APEC economies keep their codes; others become UN_<REF_AREA>.
    """
    apec_label_to_code = {
        "Australia": "01_AUS",
        "Brunei Darussalam": "02_BD",
        "Canada": "03_CDA",
        "Chile": "04_CHL",
        "China": "05_PRC",
        "China, Hong Kong Special Administrative Region": "06_HKC",
        "Indonesia": "07_INA",
        "Japan": "08_JPN",
        "Republic of Korea": "09_ROK",
        "Malaysia": "10_MAS",
        "Mexico": "11_MEX",
        "New Zealand": "12_NZ",
        "Papua New Guinea": "13_PNG",
        "Peru": "14_PE",
        "Philippines": "15_PHL",
        "Russian Federation": "16_RUS",
        "Singapore": "17_SGP",
        "Chinese Taipei": "18_CT",
        "Thailand": "19_THA",
        "United States": "20_USA",
        "Viet Nam": "21_VN",
    }
    code = apec_label_to_code.get(label)
    if code:
        return code, label
    # Fallback for non-APEC economies
    fallback_code = f"UN_{ref_area}"
    return fallback_code, label


def _classify_fuel(commodity_label: str) -> str:
    """
    Explicitly map UN commodity labels to coarse fuel buckets.
    Raises if an unmapped label is encountered.
    """
    return map_un_fuel(commodity_label)


def _classify_sector(tx_label: str, unit_measure: str | None, commodity_label: str | None) -> str | None:
    """
    Map transaction labels to target sectors.
    """
    lbl = tx_label.lower()
    commodity = (commodity_label or "").lower()
    if lbl == "production" and commodity in ELEC_PRODUCTION_LABELS:
        return "18_electricity_output_in_gwh"
    if "production" in lbl:
        return "01_production"
    if lbl == "imports":
        return "02_imports"
    if lbl == "exports":
        return "03_exports"
    if "total energy supply" in lbl:
        return "07_total_primary_energy_supply"
    if lbl.startswith("transformation"):
        return "09_total_transformation_sector"
    if lbl == "final energy consumption" or lbl == "final consumption":
        return "12_total_final_consumption"
    if "transport" in lbl:
        return "15_transport_sector"
    if "manufacturing" in lbl or "industry" in lbl:
        return "14_industry_sector"
    if "household" in lbl or "commerce" in lbl:
        return "16_buildings_sector"
    if "other" in lbl:
        return "16_other_sector"
    if "non-energy" in lbl:
        return "17_nonenergy_use"
    return None


def generate_un_assets(
    input_path: Path,
    output_json: Path,
    years: List[int],
    scenario: str,
    sectors: List[str],
    index_json: Optional[Path] = None,
    chunksize: int = 50000,
) -> int:
    """
    Aggregate UN labeled CSV (energy_obs_labeled.csv) into energy profile JSON.
    """
    year_set = {str(y) for y in years}
    totals_by_year: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {
        str(y): {} for y in years
    }
    names: Dict[str, str] = {}
    seen_fuels: Dict[str, Dict[str, set[str]]] = {str(y): {} for y in years}
    stats = {
        "skipped_unit": 0,
        "skipped_sector": 0,
        "processed_rows": 0,
    }
    prod_kept: set[str] = set()
    prod_dropped_mapped: set[str] = set()
    prod_dropped_labels: set[str] = set()
    prod_mapped: set[str] = set()

    usecols = [
        "REF_AREA",
        "REF_AREA_LABEL",
        "COMMODITY_LABEL",
        "TRANSACTION_LABEL",
        "UNIT_MEASURE",
        "TIME_PERIOD",
        "OBS_VALUE_SCALED",
        "VALUE_PJ",
    ]

    allowed_units = {"PJ", "TJ", "GWHR", "TN", "M3"}

    for chunk in pd.read_csv(input_path, usecols=usecols, chunksize=chunksize):
        chunk["TIME_PERIOD"] = chunk["TIME_PERIOD"].astype(str)
        chunk = chunk[chunk["TIME_PERIOD"].isin(year_set)]
        if chunk.empty:
            continue

        for _, row in chunk.iterrows():
            stats["processed_rows"] += 1
            year_str = str(row["TIME_PERIOD"])
            raw_lbl_full = str(row["COMMODITY_LABEL"]).strip()
            raw_lbl = raw_lbl_full.lower()
            tx_label = str(row["TRANSACTION_LABEL"])
            sector = _classify_sector(tx_label, str(row["UNIT_MEASURE"]), raw_lbl_full)
            if not sector:
                stats["skipped_sector"] += 1
                continue
            unit_measure = str(row["UNIT_MEASURE"]).upper()
            if unit_measure not in allowed_units:
                stats["skipped_unit"] += 1
                continue

            ref_area = str(row["REF_AREA"])
            area_label = str(row["REF_AREA_LABEL"])
            econ_code, econ_name = _map_economy_code(ref_area, area_label)
            names[econ_code] = econ_name

            raw_lbl_full = str(row["COMMODITY_LABEL"]).strip()
            raw_lbl = raw_lbl_full.lower()
            fuel = _classify_fuel(raw_lbl_full)
            # Value selection
            val = pd.to_numeric(row["VALUE_PJ"], errors="coerce")
            if pd.isna(val):
                continue
            if sector == "01_production":
                prod_mapped.add(fuel)
                if raw_lbl in PRODUCTION_DROP_LABELS:
                    prod_dropped_mapped.add(fuel)
                    prod_dropped_labels.add(raw_lbl)
                    continue
                if raw_lbl not in PRIMARY_PRODUCTION_LABELS_KEEP:
                    raise RuntimeError(
                        f"Production label not classified for keep/drop: {raw_lbl_full}"
                    )
                prod_kept.add(fuel)
            seen_fuels.setdefault(year_str, {}).setdefault(econ_code, set()).add(fuel)

            if sector == "03_exports":
                val = -float(val)

            econ_entry = totals_by_year[year_str].setdefault(econ_code, {})
            fuel_map = econ_entry.setdefault(sector, {})
            fuel_map[fuel] = fuel_map.get(fuel, 0.0) + float(val)

    # Net imports computation
    datasets: Dict[str, Dict] = {}
    profile_counts: List[int] = []
    for year_str in sorted(totals_by_year.keys()):
        econ_totals = totals_by_year[year_str]
        for econ_code, econ_entry in econ_totals.items():
            imports = econ_entry.get("02_imports", {})
            exports = econ_entry.get("03_exports", {})
            net: Dict[str, float] = {}
            for fuel in set(imports.keys()).union(exports.keys()):
                net[fuel] = imports.get(fuel, 0.0) + exports.get(fuel, 0.0)
            econ_entry["net_imports"] = net

        profiles: List[Dict] = []
        for econ_code in sorted(econ_totals.keys()):
            sector_data = {}
            for sector in sectors:
                fuel_map = econ_totals[econ_code].get(sector, {})
                sector_data[sector] = [
                    {"fuel": fuel, "value": float(val)}
                    for fuel, val in sorted(fuel_map.items())
                ]
            # Recompute TFC by fuel from end-use sectors
            tfc_fuels: Dict[str, float] = {}
            for part in [
                "14_industry_sector",
                "15_transport_sector",
                "16_buildings_sector",
                "16_other_sector",
                "17_nonenergy_use",
            ]:
                for f in sector_data.get(part, []):
                    tfc_fuels[f["fuel"]] = tfc_fuels.get(f["fuel"], 0.0) + f["value"]
            if tfc_fuels:
                sector_data["12_total_final_consumption"] = [
                    {"fuel": fuel, "value": val}
                    for fuel, val in sorted(tfc_fuels.items())
                ]
            sector_data = _prune_sectors(sector_data, aggregate_tfc=True)

            # Validate TFC vs sum of end-use sectors
            end_use_keys = [
                "14_industry_sector",
                "15_transport_sector",
                "16_buildings_sector",
                "16_other_sector",
                "17_nonenergy_use",
            ]
            end_use_sum = 0.0
            for k in end_use_keys:
                for f in sector_data.get(k, []):
                    end_use_sum += float(f.get("value", 0) or 0)
            tfc_sum = sum(float(f.get("value", 0) or 0) for f in sector_data.get("12_total_final_consumption", []))
            if abs(end_use_sum - tfc_sum) > max(1.0, 0.01 * abs(tfc_sum)):
                print(
                    f"[WARN] TFC mismatch for {econ_code} {year_str}: end-use sum={end_use_sum} vs tfc={tfc_sum}"
                )

            profile = _attach_metrics(
                {
                    "economy": econ_code,
                    "name": names.get(econ_code, econ_code),
                    "source": "UN",
                    "sectors": sector_data,
                },
                exports_negative=True,
            )
            _validate_metrics(profile)
            profiles.append(profile)
        datasets[year_str] = {
            "year": int(year_str),
            "scenario": scenario,
            "profiles": profiles,
        }
        profile_counts.append(len(profiles))

    expected_prod = set(UN_FUEL_MAP.values())
    unexpected = prod_mapped - expected_prod
    if unexpected:
        raise RuntimeError(
            f"Unexpected production fuels encountered (update keep/drop lists): {sorted(unexpected)}"
        )
    print(
        f"[INFO] UN aggregation rows processed: {stats['processed_rows']}, "
        f"skipped_sector: {stats['skipped_sector']}, skipped_unit: {stats['skipped_unit']}"
    )

    out_obj = {
        "years": sorted(years),
        "defaultYear": max(years),
        "scenario": scenario,
        "datasets": datasets,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(out_obj, indent=2))
    # Write economy-group shards and an index
    _write_group_shards(out_obj, output_json)

    print(
        f"[INFO] Wrote UN profiles for years {years} to {output_json} (group-sharded index)"
    )
    return sum(profile_counts)


def run_workflow(
    apec_input: Optional[str] = "data/apec_energy.xlsx",
    un_input: Optional[str] = "scripts/un_mirror/normalized/energy_obs_labeled.csv",
    output_json: str = "public/data/energy-profiles-apec.json",
    un_output_json: str = "public/data/energy-profiles-un.json",
    charts_dir: str = "public/energy-graphs",
    apec_default_year: int = 2020,
    scenario: str = "reference",
    sectors: Optional[List[str]] = None,
    un_years: Optional[List[int]] = None,
    apec_years: Optional[List[int]] = None,
    label_column: str = "economy",
    skip_charts: bool = False,
    source: str = DEFAULT_SOURCE,
) -> tuple[int, int]:
    """
    Run APEC and UN generation workflows (usable from notebooks).
    Returns (apec_count, un_count); raises if both fail/missing.
    """
    sectors = sectors or DEFAULT_SECTORS
    charts_dir_path = Path(charts_dir)

    apec_success = False
    un_success = False
    apec_count = 0
    un_count = 0
    errors: List[str] = []
    un_years = un_years or [2010, 2020]
    apec_years = apec_years or [2010, 2015, 2020, 2025, 2030, 2035, 2040, 2045, 2050, 2055, 2060]

    def _resolve(path_str: Optional[str]) -> Optional[Path]:
        if not path_str:
            return None
        p = Path(path_str).expanduser()
        if p.exists():
            return p
        # fallback to repo root relative to this file
        repo_root = Path(__file__).resolve().parent.parent
        p_alt = repo_root / path_str
        return p_alt if p_alt.exists() else p

    if apec_input:
        apec_path = _resolve(apec_input)
        if apec_path and apec_path.exists():
            try:
                if apec_path.suffix.lower() == ".csv":
                    apec_count = generate_apec_assets_csv_multi(
                        apec_path,
                        Path(output_json),
                        years=apec_years,
                        default_year=apec_default_year,
                        scenario=scenario,
                        label_column=label_column,
                    )
                else:
                    apec_count = generate_apec_assets(
                        apec_path,
                        Path(output_json),
                        charts_dir_path,
                        apec_default_year,
                        scenario,
                        sectors,
                        label_column,
                        skip_charts,
                        source=source,
                    )
                apec_success = True
            except Exception as e:  # pragma: no cover - runtime guard
                errors.append(f"APEC generation failed: {e}")
                print(f"[WARN] APEC generation failed: {e}")
        else:
            errors.append(f"APEC input not found: {apec_path}")
            print(f"[WARN] APEC input not found: {apec_path}")

    if un_input:
        un_path = _resolve(un_input)
        if un_path and un_path.exists():
            try:
                un_index = Path(un_output_json).with_name(f"{Path(un_output_json).stem}.index.json")
                un_count = generate_un_assets(
                    un_path,
                    Path(un_output_json),
                    years=un_years,
                    scenario=scenario,
                    sectors=UN_SECTORS,
                    index_json=un_index,
                )
                un_success = True
            except Exception as e:  # pragma: no cover - runtime guard
                errors.append(f"UN generation failed: {e}")
                print(f"[WARN] UN generation failed: {e}")
        else:
            errors.append(f"UN input not found: {un_path}")
            print(f"[WARN] UN input not found: {un_path}")

    if not apec_success and not un_success:
        raise RuntimeError(
            "No datasets generated; APEC and UN generations failed or missing inputs. "
            + "; ".join(errors)
        )

    # Write shared chart metadata for the frontend
    try:
        write_chart_meta(Path("src/config/chartMeta.json"))
    except Exception as e:  # pragma: no cover - runtime guard
        print(f"[WARN] Failed to write chart meta: {e}")

    return apec_count, un_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Create energy assets for the game.")
    parser.add_argument(
        "--input",
        help="[Deprecated] Path to the APEC Excel input file (use --apec-input).",
    )
    parser.add_argument(
        "--apec-input",
        default="data/apec_energy.xlsx",
        help="Path to the APEC Excel input file.",
    )
    parser.add_argument(
        "--un-input",
        default="scripts/un_mirror/normalized/energy_obs_labeled.csv",
        help="Path to the UN labeled CSV input file (optional).",
    )
    parser.add_argument(
        "--output-json",
        default="public/data/energy-profiles-apec.json",
        help="Where to write the APEC JSON dataset.",
    )
    parser.add_argument(
        "--un-output-json",
        default="public/data/energy-profiles-un.json",
        help="Where to write the UN JSON dataset (if generated).",
    )
    parser.add_argument(
        "--un-years",
        nargs="+",
        type=int,
        default=[2010, 2020],
        help="Years to aggregate for the UN dataset (default: 2010 2020).",
    )
    parser.add_argument(
        "--charts-dir",
        default="public/energy-graphs",
        help="Directory where PNG charts will be saved.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2020,
        help="Which numeric column to use for values (e.g. 2020).",
    )
    parser.add_argument(
        "--scenario",
        default="reference",
        help="Scenario to filter on (e.g. reference).",
    )
    parser.add_argument(
        "--sectors",
        nargs="+",
        default=DEFAULT_SECTORS,
        help="Sectors to keep (space separated).",
    )
    parser.add_argument(
        "--label-column",
        default="economy",
        help="Optional column that contains a human readable name (e.g. economy_name).",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Value to set in the profile's source field (default: APEC).",
    )
    parser.add_argument(
        "--skip-charts",
        action="store_true",
        help="If set, only JSON will be generated.",
    )

    args = parser.parse_args()

    run_workflow(
        apec_input=args.apec_input or args.input,
        un_input=args.un_input,
        output_json=args.output_json,
        un_output_json=args.un_output_json,
        charts_dir=args.charts_dir,
        year=args.year,
        scenario=args.scenario,
        sectors=args.sectors,
        un_years=args.un_years,
        label_column=args.label_column,
        skip_charts=args.skip_charts,
        source=args.source,
    )

#%%
if __name__ == "__main__":
    # main()
    import os
    os.chdir('../')
    run_workflow(
        apec_input="merged_file_energy_ALL_20250814.csv",
        un_input="scripts/un_mirror/normalized/energy_obs_labeled.csv",
        output_json="public/data/energy-profiles-apec.json",
        un_output_json="public/data/energy-profiles-un.json",
        scenario="reference",
        sectors=None,  # uses defaults
        skip_charts=True,
    )

#%%
