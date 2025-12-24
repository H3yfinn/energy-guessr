#!/usr/bin/env python3
#%%
"""
Run energy dataset preparation for APEC and UN in one shot.

This replaces the old JS prestart/prebuild hook; run manually when you need to
refresh public/data/energy-profiles*.json.

Examples:
  python scripts/run_energy_prep.py
  python scripts/run_energy_prep.py --apec-input data/apec_energy.xlsx --un-input scripts/un_mirror/normalized/energy_obs_labeled.csv
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from create_energy_assets import run_workflow
from combine_un_ei import combine_un_with_ei


def _delete_un_only_outputs(un_output: Path) -> None:
    """
    Remove UN-only JSON, index, and shards after a successful UN+EI build.
    """
    un_path = un_output
    un_index = un_path.with_name(f"{un_path.stem}.index.json")
    shard_glob = f"{un_path.stem}-*-g*.json"
    try:
        if un_path.exists():
            un_path.unlink()
        if un_index.exists():
            un_index.unlink()
        for shard in un_path.parent.glob(shard_glob):
            shard.unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - runtime guard
        print(f"[WARN] Failed to delete UN-only files: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare APEC/UN energy datasets.")
    parser.add_argument(
        "--apec-input",
        default="data/apec_energy.xlsx",
        help="Path to APEC balances file (CSV or Excel).",
    )
    parser.add_argument(
        "--un-input",
        default="scripts/un_mirror/normalized/energy_obs_labeled.csv",
        help="Path to UN labeled CSV (energy_obs_labeled.csv).",
    )
    parser.add_argument(
        "--output-json",
        default="public/data/energy-profiles-apec.json",
        help="APEC output JSON path.",
    )
    parser.add_argument(
        "--un-output-json",
        default="public/data/energy-profiles-un.json",
        help="UN output JSON path.",
    )
    parser.add_argument(
        "--un-ei-output-json",
        default="public/data/energy-profiles-un-ei.json",
        help="UN+EI output JSON path (uses EI electricity by fuel).",
    )
    parser.add_argument(
        "--ei-workbook",
        default="EI-Stats-Review-ALL-data.xlsx",
        help="Path to EI-Stats-Review-ALL-data.xlsx for electricity by fuel.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2020,
        help="APEC default year (for Excel) / defaultYear (for APEC CSV output).",
    )
    parser.add_argument(
        "--scenario",
        default="reference",
        help="Scenario filter for APEC and UN (if applicable).",
    )
    parser.add_argument(
        "--un-years",
        nargs="+",
        type=int,
        default=[2010, 2020],
        help="Years to aggregate for the UN dataset (default: 2010 2020).",
    )
    parser.add_argument(
        "--skip-charts",
        action="store_true",
        help="Skip chart generation for APEC output.",
    )
    args = parser.parse_args()

    apec_count, un_count = run_workflow(
        apec_input=args.apec_input,
        un_input=args.un_input,
        output_json=args.output_json,
        un_output_json=args.un_output_json,
        charts_dir="public/energy-graphs",
        apec_default_year=args.year,
        scenario=args.scenario,
        un_years=args.un_years,
        skip_charts=args.skip_charts,
    )
    print(f"APEC profiles: {apec_count}, UN profiles: {un_count}")

    # Always produce UN+EI electricity overlay (drops economies without EI data)
    try:
        combine_un_with_ei(
            Path(args.un_output_json),
            Path(args.ei_workbook),
            Path(args.un_ei_output_json),
        )
        _delete_un_only_outputs(Path(args.un_output_json))
    except Exception as exc:  # pragma: no cover - runtime guard
        print(f"[WARN] Failed to combine UN with EI electricity: {exc}")


def run_energy_prep_notebook(
    apec_input: str = "data/apec_energy.xlsx",
    un_input: str = "scripts/un_mirror/normalized/energy_obs_labeled.csv",
    ei_workbook: str = "EI-Stats-Review-ALL-data.xlsx",
    apec_output: str = "public/data/energy-profiles-apec.json",
    un_output: str = "public/data/energy-profiles-un.json",
    un_ei_output: str = "public/data/energy-profiles-un-ei.json",
    apec_years=None,
    un_years=None,
    apec_default_year: int = 2020,
    scenario: str = "reference",
    skip_charts: bool = True,
):
    """
    Convenience hook for notebooks: runs APEC + UN + UN+EI prep and returns (apec_count, un_count).
    """
    apec_years = apec_years or [2010, 2015, 2020, 2025, 2030, 2035, 2040, 2045, 2050, 2055, 2060]
    un_years = un_years or [2010, 2020]
    apec_count, un_count = run_workflow(
        apec_input=apec_input,
        un_input=un_input,
        output_json=apec_output,
        un_output_json=un_output,
        charts_dir="public/energy-graphs",
        apec_default_year=apec_default_year,
        scenario=scenario,
        un_years=un_years,
        apec_years=apec_years,
        skip_charts=skip_charts,
    )
    combine_un_with_ei(Path(un_output), Path(ei_workbook), Path(un_ei_output))
    _delete_un_only_outputs(Path(un_output))
    return apec_count, un_count


if __name__ == "__main__":
    #DONT DELETE THIS COMMENT OUT - FOR DEBUGGING PURPOSES ONLY
    # os.chdir('../')
    # run_energy_prep_notebook(
    # apec_input="merged_file_energy_ALL_20250814.csv",
    # un_input="scripts/un_mirror/normalized/energy_obs_labeled.csv",
    # ei_workbook="EI-Stats-Review-ALL-data.xlsx",
    # skip_charts=True,
    # )
    #DONT DELETE THIS COMMENT OUT - FOR DEBUGGING PURPOSES ONLY
    main()
#%%
