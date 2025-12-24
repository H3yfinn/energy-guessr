#!/usr/bin/env python3
"""
Combine UN multi-year data (2010/2020) with Energy Institute electricity-by-fuel
data (2023) into a single JSON compatible with the app.

Electricity generation is overridden with EI 2023 values for economies where EI
data exists; others are dropped from the combined output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Reuse helpers and shared logic
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for p in (SCRIPT_DIR, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.append(str(p))
import create_energy_assets as prep  # type: ignore  # noqa: E402
import mappings  # type: ignore  # noqa: E402

EI_ELEC_SHEET = "Elec generation by fuel"


def _load_un_base(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"UN JSON not found: {path}")
    return json.loads(path.read_text())


def _extract_name_lookup(un_obj: dict) -> Dict[str, tuple[str, str]]:
    """
    Build a lookup of lowercase economy name -> (code, display name)
    using any year present in the UN payload.
    """
    lookup: Dict[str, tuple[str, str]] = {}
    datasets = un_obj.get("datasets", {})
    for data in datasets.values():
        for profile in data.get("profiles", []):
            name = str(profile.get("name", "")).strip()
            code = str(profile.get("economy", "")).strip()
            if not name or not code:
                continue
            lookup.setdefault(name.lower(), (code, name))
    return lookup


def _extract_ei_electricity(
    workbook: Path, name_lookup: Dict[str, tuple[str, str]]
) -> Dict[str, List[Dict[str, float]]]:
    """
    Parse EI electricity-by-fuel sheet (base columns = 2023) and return
    {econ_code: [{fuel, value}, ...]} with PJ values, mapped to UN codes.
    """
    df = pd.read_excel(workbook, sheet_name=EI_ELEC_SHEET, header=2)
    df = df.rename(columns={df.columns[0]: "economy"})
    df = df.dropna(subset=["economy"])

    # Filter out obvious aggregates/regions
    blacklist_prefixes = tuple(mappings.EI_ELEC_BLACKLIST_PREFIXES)
    alias_map = mappings.EI_NAME_ALIASES
    fuel_map = mappings.EI_ELEC_FUEL_MAP

    fuel_cols = [col for col in df.columns if not col.endswith(".1") and col in fuel_map]
    if not fuel_cols:
        raise RuntimeError("No expected fuel columns found in EI electricity sheet")

    out: Dict[str, List[Dict[str, float]]] = {}
    for _, row in df.iterrows():
        econ_label = str(row["economy"]).strip()
        if not econ_label or econ_label.startswith(blacklist_prefixes):
            continue
        key = econ_label.lower()
        match = name_lookup.get(key) or name_lookup.get(alias_map.get(key, ""))
        if not match:
            continue
        econ_code, _ = match
        fuels: Dict[str, float] = {}
        for raw in fuel_cols:
            val = pd.to_numeric(row[raw], errors="coerce")
            if pd.isna(val):
                continue
            fuels[fuel_map[raw]] = fuels.get(fuel_map[raw], 0.0) + float(val) * 3.6
        if not fuels:
            continue
        out[econ_code] = [{"fuel": f, "value": v} for f, v in sorted(fuels.items())]
    return out


def _overlay_electricity(
    datasets: Dict[str, dict],
    ei_elec: Dict[str, List[Dict[str, float]]],
    scenario_label: str,
) -> Dict[str, dict]:
    """
    Replace electricity generation with EI values and drop economies without EI data.
    """
    updated: Dict[str, dict] = {}
    for year_str, data in datasets.items():
        profiles_out: List[Dict] = []
        for profile in data.get("profiles", []):
            econ = profile.get("economy")
            if econ not in ei_elec:
                continue
            sectors = dict(profile.get("sectors", {}))
            sectors["18_electricity_output_in_gwh"] = ei_elec[econ]
            new_profile = {
                **profile,
                "source": "UN+EI (elec 2023)",
                "sectors": sectors,
            }
            new_profile.pop("metrics", None)
            new_profile = prep._attach_metrics(new_profile, exports_negative=True)
            prep._validate_metrics(new_profile)
            profiles_out.append(new_profile)
        updated[year_str] = {
            **data,
            "profiles": profiles_out,
            "scenario": scenario_label,
        }
    return updated


def combine_un_with_ei(
    un_json: Path,
    ei_workbook: Path,
    output_json: Path,
    scenario_label: str = "UN (2010/2020) + EI electricity (2023)",
) -> int:
    un_obj = _load_un_base(un_json)
    name_lookup = _extract_name_lookup(un_obj)
    ei_elec = _extract_ei_electricity(ei_workbook, name_lookup)

    datasets = _overlay_electricity(dict(un_obj.get("datasets", {})), ei_elec, scenario_label)
    years = sorted({int(y) for y in datasets.keys()})
    default_year = un_obj.get("defaultYear", years[-1] if years else None) or years[-1]
    combined = {
        "years": years,
        "defaultYear": default_year,
        "scenario": scenario_label,
        "datasets": datasets,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(combined, indent=2))
    prep._write_group_shards(combined, output_json)
    print(f"[INFO] Wrote combined UN+EI dataset to {output_json} (profiles_with_elec={len(ei_elec)})")
    return sum(len(d.get("profiles", [])) for d in datasets.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine UN data with EI electricity (2023).")
    parser.add_argument(
        "--un-json",
        default="public/data/energy-profiles-un.json",
        dest="un_json",
        help="Existing UN multi-year JSON (e.g., 2010/2020).",
    )
    parser.add_argument(
        "--ei-workbook",
        default="EI-Stats-Review-ALL-data.xlsx",
        help="Path to EI-Stats-Review-ALL-data.xlsx",
    )
    parser.add_argument(
        "--output-json",
        default="public/data/energy-profiles-un-ei.json",
        help="Where to write the combined JSON.",
    )
    args = parser.parse_args()

    combine_un_with_ei(Path(args.un_json), Path(args.ei_workbook), Path(args.output_json))


if __name__ == "__main__":
    main()
