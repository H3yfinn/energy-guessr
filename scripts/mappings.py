"""
Centralized fuel/sector mappings for energy asset generation.
Keeping this in one place reduces drift when adding new datasets or labels.
"""
from __future__ import annotations

from typing import Dict, Set

CHART_FUELS: Set[str] = {
    "coal",
    "oil",
    "gas",
    "electricity",
    "renewables_and_others",
    "wind_solar",
    "thermal",
    "hydro",
    "solar",
    "wind",
    "tide",
    "nuclear",
    "geothermal",
}

# Canonical chart metadata (single source of truth for fuels/colors/order).
# Extend here when adding new fuels.
CHART_META = {
    "fuels": [
        {"key": "coal", "color": "#1f2933", "order": 0},
        {"key": "oil", "color": "#b05b1d", "order": 1},
        {"key": "gas", "color": "#1c7ed6", "order": 2},
        {"key": "thermal", "color": "#7c4dff", "order": 3},
        {"key": "hydro", "color": "#0ea5e9", "order": 4},
        {"key": "solar", "color": "#f59e0b", "order": 5},
        {"key": "wind", "color": "#22c55e", "order": 6},
        {"key": "tide", "color": "#10b981", "order": 7},
        {"key": "nuclear", "color": "#8b5cf6", "order": 8},
        {"key": "geothermal", "color": "#14b8a6", "order": 9},
        {"key": "wind_solar", "color": "#22c55e", "order": 10},
        {"key": "renewables_and_others", "color": "#2e8b57", "order": 11},
        {"key": "electricity", "color": "#7b1fa2", "order": 99, "hide_in_elec_gen": True},
        {"key": "net_imports", "color": "#0d9488", "order": 100},
        {"key": "industry", "color": "#4b5563", "order": 101},
        {"key": "transport", "color": "#f97316", "order": 102},
        {"key": "buildings", "color": "#eab308", "order": 103},
        {"key": "non_energy_use", "color": "#db2777", "order": 104},
        {"key": "others", "color": "#94a3b8", "order": 105},
    ]
}

# Map UN COMMODITY_LABEL (lowercased) -> coarse fuel bucket
UN_FUEL_MAP: Dict[str, str] = {
    # Oil / refined
    "additives and oxygenates": "oil",
    "aviation gasoline": "oil",
    "bio jet kerosene": "renewables_and_others",
    "biodiesel": "renewables_and_others",
    "biogasoline": "renewables_and_others",
    "bitumen": "oil",
    "fuel oil": "oil",
    "gas oil/ diesel oil": "oil",
    "gasoline-type jet fuel": "oil",
    "kerosene-type jet fuel": "oil",
    "liquified petroleum gas": "oil",
    "lubricants": "oil",
    "motor gasoline": "oil",
    "naphtha": "oil",
    "natural gas liquids": "gas",
    "oil shale / oil sands": "oil",
    "other kerosene": "oil",
    "other liquid biofuels": "renewables_and_others",
    "other oil products n.e.c.": "oil",
    "other hydrocarbons": "oil",
    "paraffin waxes": "oil",
    "petroleum coke": "oil",
    "refinery feedstocks": "oil",
    "refinery gas": "gas",
    "total refinery output": "oil",
    "white spirit and special boiling point industrial spirits": "oil",
    # Coal / coal products
    "anthracite": "coal",
    "brown coal": "coal",
    "brown coal briquettes": "coal",
    "coking coal": "coal",
    "hard coal": "coal",
    "lignite": "coal",
    "other bituminous coal": "coal",
    "other coal products": "coal",
    "peat": "coal",
    "peat products": "coal",
    "patent fuel": "coal",
    "coal tar": "coal",
    "coke oven coke": "coal",
    "gas coke": "coal",
    "sub-bituminous coal": "coal",
    # Gas / coal gases / by-product gases
    "blast furnace gas": "gas",
    "coke oven gas": "gas",
    "gasworks gas": "gas",
    "other recovered gases": "gas",
    "natural gas (including lng)": "gas",
    "ethane": "gas",
    # Electricity / capacity / generation techs
    "thermal electricity": "thermal",
    "total electricity": "electricity",
    "total capacity: main activity producers and autoproducers": "electricity",
    "total capacity, main activity producers": "electricity",
    "nuclear electricity": "nuclear",
    "hydro, main activity producers": "hydro",
    "hydro, total": "hydro",
    "hydro": "hydro",
    "wind electricity": "wind",
    "solar electricity": "solar",
    "tide, wave and ocean electricity": "tide",
    "geothermal electricity": "geothermal",
    # Renewables / biomass
    "animal waste": "renewables_and_others",
    "bagasse": "renewables_and_others",
    "biogases": "renewables_and_others",
    "black liquor": "renewables_and_others",
    "charcoal": "renewables_and_others",
    "combustible renewables, total": "renewables_and_others",
    "direct use of geothermal heat": "geothermal",
    "direct use of solar thermal heat": "renewables_and_others",
    "falling water": "hydro",
    "fuelwood": "renewables_and_others",
    "geothermal": "geothermal",
    "heat": "renewables_and_others",
    "heat from combustible fuels": "renewables_and_others",
    "industrial waste": "renewables_and_others",
    "municipal wastes": "renewables_and_others",
    "of which: bio jet kerosene": "renewables_and_others",
    "of which: biodiesel": "renewables_and_others",
    "of which: biogasoline": "renewables_and_others",
    "other vegetal material and residues": "renewables_and_others",
    "solar electricity": "solar",
    "tide, wave and ocean electricity": "tide",
    "uranium": "renewables_and_others",
    "wind electricity": "wind",
    # Generic/aggregate
    "combustible fuels, main activity producers": "renewables_and_others",
    "combustible fuels, total": "renewables_and_others",
    "conventional crude oil": "oil",
}

# Labels to drop from production (secondary/refined/aggregate)
PRODUCTION_DROP_LABELS: Set[str] = {
    "additives and oxygenates",
    "aviation gasoline",
    "bio jet kerosene",
    "biodiesel",
    "biogasoline",
    "bitumen",
    "blast furnace gas",
    "brown coal briquettes",
    "coal tar",
    "coke oven coke",
    "coke oven gas",
    "combustible fuels, main activity producers",
    "combustible fuels, total",
    "electricity, net installed capacity of electric power plants",
    "fuel oil",
    "gas coke",
    "gas oil/ diesel oil",
    "gasoline-type jet fuel",
    "heat",
    "heat from combustible fuels",
    "kerosene-type jet fuel",
    "liquified petroleum gas",
    "lubricants",
    "motor gasoline",
    "naphtha",
    "natural gas liquids",
    "nuclear electricity",
    "of which: bio jet kerosene",
    "of which: biodiesel",
    "of which: biogasoline",
    "other kerosene",
    "other liquid biofuels",
    "other oil products n.e.c.",
    "paraffin waxes",
    "petroleum coke",
    "refinery feedstocks",
    "refinery gas",
    "total refinery output",
    "total electricity",
    "total capacity: main activity producers and autoproducers",
    "total capacity, main activity producers",
    "white spirit and special boiling point industrial spirits",
    "other recovered gases",
    "thermal electricity",
}

PRIMARY_PRODUCTION_LABELS_KEEP: Set[str] = set(UN_FUEL_MAP.keys()) - PRODUCTION_DROP_LABELS
PRODUCTION_FUEL_KEEP: Set[str] = {"coal", "oil", "gas", "renewables_and_others"}
UN_MAPPED_FUELS: Set[str] = set(UN_FUEL_MAP.values())

ELEC_PRODUCTION_LABELS: Set[str] = {
    "total electricity",
    "nuclear electricity",
    "solar electricity",
    "wind electricity",
    "tide, wave and ocean electricity",
    "thermal electricity",
    "hydro",
    "hydro, total",
    "hydro, main activity producers",
    "geothermal electricity",
}


def map_un_fuel(label: str) -> str:
    key = label.strip().lower()
    mapped = UN_FUEL_MAP.get(key)
    if not mapped:
        raise RuntimeError(f"Unmapped UN fuel label: {label}")
    return mapped


def is_production_dropped(label: str) -> bool:
    return label.strip().lower() in PRODUCTION_DROP_LABELS


def is_production_kept(label: str) -> bool:
    key = label.strip().lower()
    return key in PRIMARY_PRODUCTION_LABELS_KEEP and not is_production_dropped(label)


def write_chart_meta(path: str | Path) -> None:
    """
    Write chart metadata to JSON so the frontend can consume a single source of truth.
    """
    from pathlib import Path as _Path
    import json as _json

    _Path(path).write_text(_json.dumps(CHART_META, indent=2))


# Energy Institute helpers (electricity by fuel sheet)
EI_ELEC_FUEL_MAP: Dict[str, str] = {
    "Oil": "oil",
    "Natural Gas": "gas",
    "Coal": "coal",
    "Nuclear energy": "nuclear",
    "Hydro electric": "hydro",
    "Renewables": "renewables_and_others",
    "Other#": "renewables_and_others",
}

EI_ELEC_BLACKLIST_PREFIXES: Set[str] = {
    "Total ",
    "Other ",
    "Spot ",
    "Net ",
    "Imports",
    "Exports",
}

# Lowercase keys -> canonical UN name for easier matching
EI_NAME_ALIASES: Dict[str, str] = {
    "us": "united states",
    "u.s.": "united states",
    "usa": "united states",
    "viet nam": "vietnam",
    "uae": "united arab emirates",
    "south korea": "republic of korea",
}
