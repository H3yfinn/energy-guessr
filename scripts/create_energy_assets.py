#!/usr/bin/env python3
"""
Turn an energy balances Excel file into ready-to-use assets for the app.

Example:
python scripts/create_energy_assets.py ^
  --input ./data/australia_balances.xlsx ^
  --output-json ./public/data/energy-profiles.json ^
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
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_SECTORS = [
    "07_total_primary_energy_supply",
    "12_total_final_consumption",
    "09_total_transformation_sector",
]


def build_profile(
    df: pd.DataFrame, economy: str, sectors: Iterable[str], year: int, label_column: str
) -> Dict:
    profile: Dict = {
        "economy": economy,
        "name": str(df[df["economy"] == economy][label_column].iloc[0])
        if label_column in df.columns
        else economy,
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
            {"fuel": row["fuels"], "value": float(row[year])}
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Create energy assets for the game.")
    parser.add_argument("--input", required=True, help="Path to the Excel input file.")
    parser.add_argument(
        "--output-json",
        default="public/data/energy-profiles.json",
        help="Where to write the JSON dataset.",
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
        "--skip-charts",
        action="store_true",
        help="If set, only JSON will be generated.",
    )

    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    output_json = Path(args.output_json)

    df = pd.read_excel(args.input)
    filtered = df[(df["scenarios"] == args.scenario) & (df["sectors"].isin(args.sectors))]

    economies = sorted(filtered["economy"].unique())
    profiles: List[Dict] = []

    for economy in economies:
        profile = build_profile(filtered, economy, args.sectors, args.year, args.label_column)
        if not args.skip_charts:
            profile["chartImage"] = render_charts(profile, args.sectors, args.year, charts_dir)
        profiles.append(profile)

    dataset = {
        "year": args.year,
        "scenario": args.scenario,
        "sectors": args.sectors,
        "profiles": profiles,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(dataset, indent=2))
    print(f"Wrote {len(profiles)} profiles to {output_json}")


if __name__ == "__main__":
    main()
