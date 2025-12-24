#%% imports
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import time
from typing import Iterable, Optional

import requests
import pandas as pd

#%% config
@dataclass(frozen=True)
class UNDataConfig:
    base_rest: str = "https://data.un.org/WS/rest"
    agency: str = "UNSD"
    dataflow: str = "DF_UNDATA_ENERGY"
    # Key order (per UNSD docs): FREQ.REF_AREA.COMMODITY.TRANSACTION
    # We omit FREQ and leave COMMODITY/TRANSACTION blank to mean "all".
    # Key becomes: .{REF_AREA}.../
    out_raw_dir: Path = Path("un_mirror/raw_sdmx")
    out_manifest: Path = Path("un_mirror/manifest.json")
    sleep_s: float = 0.25
    timeout_s: int = 180
    max_retries: int = 3
    retry_backoff_s: float = 5.0

CFG = UNDataConfig()

#%% helpers
def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sdmx_get(url: str, accept: str, timeout_s: int) -> requests.Response:
    headers = {"Accept": accept}
    r = requests.get(url, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    return r

def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"downloads": {}}
    return json.loads(path.read_text(encoding="utf-8"))

def save_manifest(path: Path, manifest: dict) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

#%% codelists (REF_AREA)
def list_ref_areas_from_codelist(cfg: UNDataConfig) -> list[str]:
    """
    Pulls the UNSD energy AREA codelist and returns numeric REF_AREA codes.
    This codelist includes countries/areas and may include aggregates; we keep numeric IDs.
    """
    # SDMX codelist endpoint
    url = f"{cfg.base_rest}/codelist/{cfg.agency}/CL_AREA_NRG/?references=none"
    xml = sdmx_get(url, accept="application/xml", timeout_s=cfg.timeout_s).text

    # Namespaced XML uses structure:Code, so match any tag ending with "Code"
    codes: list[str] = []
    root = ET.fromstring(xml)
    for elem in root.iter():
        if elem.tag.endswith("Code"):
            code = elem.attrib.get("id")
            if code and code.isdigit():
                codes.append(code)

    return sorted(set(codes))

def fetch_codelist_map(code_id: str, cfg: UNDataConfig) -> dict[str, str]:
    """
    Fetches a SDMX codelist (e.g., CL_COMMODITY_NRG) and returns {code: name}.
    """
    url = f"{cfg.base_rest}/codelist/{cfg.agency}/{code_id}/?references=none"
    xml = sdmx_get(url, accept="application/xml", timeout_s=cfg.timeout_s).text
    root = ET.fromstring(xml)
    out: dict[str, str] = {}
    for elem in root.iter():
        if elem.tag.endswith("Code"):
            code = elem.attrib.get("id")
            label = None
            for child in elem:
                if child.tag.endswith("Name"):
                    label = child.text
                    break
            if code and label:
                out[code] = label
    return out

#%% download logic
def build_data_url_for_area(
    cfg: UNDataConfig,
    ref_area: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> str:
    # SDMX REST data endpoint:
    # /data/{agency},{dataflow},/KEY?startPeriod=YYYY&endPeriod=YYYY&format=structurespecificdata
    base = f"{cfg.base_rest}/data/{cfg.agency},{cfg.dataflow},/"
    key = f".{ref_area}.../"  # omit FREQ; REF_AREA fixed; COMMODITY & TRANSACTION wildcard
    params = ["format=structurespecificdata"]
    if start_year is not None:
        params.append(f"startPeriod={start_year}")
    if end_year is not None:
        params.append(f"endPeriod={end_year}")
    return base + key + "?" + "&".join(params)

def download_area_slice(
    cfg: UNDataConfig,
    ref_area: str,
    start_year: Optional[int],
    end_year: Optional[int],
    force: bool = False,
) -> Path:
    """
    Downloads one "slice" (area + optional time window) and stores XML to disk.
    Uses the manifest to skip already-downloaded identical slices unless force=True.
    """
    manifest = load_manifest(cfg.out_manifest)
    downloads = manifest.setdefault("downloads", {})

    slice_id = f"{ref_area}:{start_year or 'NA'}-{end_year or 'NA'}"
    if (not force) and slice_id in downloads and downloads[slice_id].get("status") == "ok":
        return Path(downloads[slice_id]["path"])

    url = build_data_url_for_area(cfg, ref_area, start_year, end_year)
    accept = "application/vnd.sdmx.structurespecificdata+xml;version=2.1"

    # Fetch with retry/backoff for transient network issues
    last_exc: requests.RequestException | None = None
    for attempt in range(cfg.max_retries):
        try:
            r = sdmx_get(url, accept=accept, timeout_s=cfg.timeout_s)
            break
        except requests.RequestException as e:
            last_exc = e
            is_last = attempt + 1 >= cfg.max_retries
            if is_last:
                raise
            delay = cfg.retry_backoff_s * (2**attempt)
            print(f"[WARN] attempt {attempt + 1}/{cfg.max_retries} failed for {slice_id}, retrying in {delay:.1f}s: {e}")
            time.sleep(delay)
    else:  # defensive: loop exits via break/raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected retry loop exit")

    content = r.content
    sha = _sha256_bytes(content)

    out_path = cfg.out_raw_dir / f"{cfg.dataflow}_area_{ref_area}_{start_year or 'NA'}_{end_year or 'NA'}.xml"
    _ensure_parent(out_path)
    out_path.write_bytes(content)

    downloads[slice_id] = {
        "status": "ok",
        "ref_area": ref_area,
        "start_year": start_year,
        "end_year": end_year,
        "url": url,
        "path": str(out_path),
        "sha256": sha,
        "bytes": len(content),
        "downloaded_at_epoch": int(time.time()),
    }
    save_manifest(cfg.out_manifest, manifest)

    time.sleep(cfg.sleep_s)
    return out_path

def iter_year_windows(start: int, end: int, window: int) -> Iterable[tuple[int, int]]:
    """
    Inclusive year windows [a,b] stepping by `window`.
    """
    y = start
    while y <= end:
        a = y
        b = min(end, y + window - 1)
        yield a, b
        y = b + 1

#%% workflow: mirror everything
def mirror_all_areas(
    cfg: UNDataConfig,
    start_year: int,
    end_year: int,
    year_window: int = 10,
    force: bool = False,
) -> None:
    """
    Mirrors the entire dataset by:
      - listing REF_AREA codes
      - downloading per area in year windows (keeps file sizes manageable)
    """
    ref_areas = list_ref_areas_from_codelist(cfg)
    print(f"REF_AREA codes found: {len(ref_areas)}")

    total_jobs = len(ref_areas) * len(list(iter_year_windows(start_year, end_year, year_window)))
    job_i = 0

    for ref_area in ref_areas:
        for a, b in iter_year_windows(start_year, end_year, year_window):
            job_i += 1
            try:
                p = download_area_slice(cfg, ref_area, a, b, force=force)
                if job_i % 50 == 0:
                    print(f"{job_i}/{total_jobs} ok (latest: {p.name})")
            except (requests.HTTPError, requests.RequestException) as e:
                # Record failure in manifest, continue
                manifest = load_manifest(cfg.out_manifest)
                downloads = manifest.setdefault("downloads", {})
                slice_id = f"{ref_area}:{a}-{b}"
                downloads[slice_id] = {
                    "status": "error",
                    "ref_area": ref_area,
                    "start_year": a,
                    "end_year": b,
                    "error": str(e),
                    "failed_at_epoch": int(time.time()),
                }
                save_manifest(cfg.out_manifest, manifest)
                print(f"[WARN] failed {slice_id}: {e}")

#%% optional: normalize to parquet (fast querying later)
def parse_structurespecific_minimal(xml_path: Path) -> pd.DataFrame:
    """
    Minimal parser that extracts observations using pandas read_xml.
    This works for many StructureSpecific SDMX files but can break if schema varies.
    If it fails, keep raw XML mirrored and parse with a dedicated SDMX library.
    """
    # The observation nodes are often <Obs> carrying data in attributes.
    # Try pandas first, then fall back to a manual ElementTree parse.
    try:
        obs = pd.read_xml(xml_path, xpath=".//Obs")
        if obs is not None and not obs.empty:
            return obs
    except Exception:
        pass

    # Manual fallback: grab <Obs> nodes and turn their attributes into rows.
    try:
        root = ET.parse(xml_path).getroot()
        rows = [dict(elem.attrib) for elem in root.iter() if elem.tag.endswith("Obs")]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()

def parse_structurespecific_with_series(xml_path: Path) -> pd.DataFrame:
    """
    Parses StructureSpecific XML and merges Series attributes into each Obs row.
    """
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return pd.DataFrame()

    rows = []
    for series in root.iter():
        if not series.tag.endswith("Series"):
            continue
        sattrs = dict(series.attrib)
        for obs in series.iter():
            if not obs.tag.endswith("Obs"):
                continue
            row = {**sattrs, **obs.attrib}
            rows.append(row)
    return pd.DataFrame(rows)

def build_energy_codelists(cfg: UNDataConfig) -> dict[str, dict[str, str]]:
    """
    Fetches the key energy codelists and returns a mapping per dimension.
    """
    id_map = {
        "REF_AREA": "CL_AREA_NRG",
        "COMMODITY": "CL_COMMODITY_NRG",
        "TRANSACTION": "CL_TRANSACTION_NRG",
        "UNIT_MEASURE": "CL_UNIT_NRG",
    }
    out: dict[str, dict[str, str]] = {}
    for col, code_id in id_map.items():
        try:
            out[col] = fetch_codelist_map(code_id, cfg)
        except requests.RequestException as e:
            print(f"[WARN] failed to fetch {code_id}: {e}")
    return out

def _enrich_labels_and_numeric(df: pd.DataFrame, label_maps: dict[str, dict[str, str]]) -> pd.DataFrame:
    """
    Adds label columns, scaled numeric values (OBS_VALUE_SCALED), and PJ conversions when possible.
    """
    if df.empty:
        return df

    for col, cmap in label_maps.items():
        if col in df.columns:
            df[f"{col}_LABEL"] = df[col].map(cmap)

    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE_NUM"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    if "UNIT_MULT" in df.columns:
        df["UNIT_MULT_INT"] = pd.to_numeric(df["UNIT_MULT"], errors="coerce")
    if "OBS_VALUE_NUM" in df.columns and "UNIT_MULT_INT" in df.columns:
        df["OBS_VALUE_SCALED"] = df["OBS_VALUE_NUM"] * (10 ** df["UNIT_MULT_INT"].fillna(0))

    # Convert to petajoules
    unit_to_pj = {
        "PJ": 1.0,
        "TJ": 1 / 1000.0,
        "GWHR": 0.0036,  # 1 GWh = 3.6 TJ
    }
    commodity_gj_per_tonne = {
        "0100": 25.8,  # Hard Coal (matches sample conversion factor in feed)
        "0110": 27.0,  # Anthracite
        "0121": 28.0,  # Coking coal
        "0129": 25.0,  # Other bituminous coal
        "0200": 10.0,  # Brown coal / lignite (typical low CV)
    }
    commodity_gj_per_m3 = {
        "2300": 0.038,  # Natural gas (approx 38 MJ/m3)
    }

    df["VALUE_PJ"] = pd.NA

    if "UNIT_MEASURE" in df.columns:
        factors = df["UNIT_MEASURE"].map(unit_to_pj)
        if "OBS_VALUE_SCALED" in df.columns:
            df["VALUE_PJ"] = df["OBS_VALUE_SCALED"] * factors
        elif "OBS_VALUE_NUM" in df.columns:
            df["VALUE_PJ"] = df["OBS_VALUE_NUM"] * factors

    # Fallback: if VALUE_PJ still missing and CONVERSION_FACTOR provided (assume GJ/unit)
    if "VALUE_PJ" in df.columns and "CONVERSION_FACTOR" in df.columns:
        mask = df["VALUE_PJ"].isna()
        if mask.any():
            conv = pd.to_numeric(df.loc[mask, "CONVERSION_FACTOR"], errors="coerce")
            if "OBS_VALUE_SCALED" in df.columns:
                qty = df.loc[mask, "OBS_VALUE_SCALED"]
            else:
                qty = df.loc[mask, "OBS_VALUE_NUM"]
            df.loc[mask, "VALUE_PJ"] = qty * conv / 1_000_000  # GJ -> PJ

    # Fallback: commodity-based calorific values for TN and M3 when no conversion factor present
    if "VALUE_PJ" in df.columns and "UNIT_MEASURE" in df.columns and "COMMODITY" in df.columns:
        # Tonnes
        mask_tn = df["VALUE_PJ"].isna() & (df["UNIT_MEASURE"] == "TN")
        if mask_tn.any():
            gj_per_tonne = df.loc[mask_tn, "COMMODITY"].map(commodity_gj_per_tonne)
            qty = df.loc[mask_tn, "OBS_VALUE_SCALED"]
            df.loc[mask_tn, "VALUE_PJ"] = qty * gj_per_tonne / 1_000_000
        # Cubic meters
        mask_m3 = df["VALUE_PJ"].isna() & (df["UNIT_MEASURE"] == "M3")
        if mask_m3.any():
            gj_per_m3 = df.loc[mask_m3, "COMMODITY"].map(commodity_gj_per_m3)
            qty = df.loc[mask_m3, "OBS_VALUE_SCALED"]
            df.loc[mask_m3, "VALUE_PJ"] = qty * gj_per_m3 / 1_000_000
    return df

def normalize_mirror_to_parquet(
    raw_dir: Path,
    out_parquet: Path = Path("un_mirror/normalized/energy_obs.parquet"),
) -> None:
    """
    Converts mirrored XML slices into one Parquet dataset.
    Keeps it simple: concatenates per-file Obs tables.
    """
    files = sorted(raw_dir.glob("*.xml"))
    _ensure_parent(out_parquet)

    chunks = []
    for i, f in enumerate(files, start=1):
        df = parse_structurespecific_with_series(f)
        if not df.empty:
            df["__source_file"] = f.name
            chunks.append(df)
        if i % 100 == 0:
            print(f"parsed {i}/{len(files)}")

    if not chunks:
        raise RuntimeError("No observations parsed. Keep raw XML and use an SDMX parser library instead.")

    out = pd.concat(chunks, ignore_index=True)
    out.to_parquet(out_parquet, index=False)
    print(f"Wrote {len(out):,} rows to {out_parquet}")

def export_mirror_to_csv(
    raw_dir: Path,
    out_csv: Path = Path("un_mirror/normalized/energy_obs.csv"),
) -> None:
    """
    Converts mirrored XML slices into one CSV file.
    Writes incrementally to avoid holding everything in memory.
    """
    files = sorted(raw_dir.glob("*.xml"))
    _ensure_parent(out_csv)
    if out_csv.exists():
        out_csv.unlink()

    rows_written = 0
    for i, f in enumerate(files, start=1):
        df = parse_structurespecific_with_series(f)
        if not df.empty:
            df["__source_file"] = f.name
            df.to_csv(out_csv, mode="a", header=not out_csv.exists(), index=False)
            rows_written += len(df)
        if i % 100 == 0:
            print(f"csv: processed {i}/{len(files)} files")

    if rows_written == 0:
        raise RuntimeError("No observations parsed; CSV not written.")
    print(f"Wrote {rows_written:,} rows to {out_csv}")

def export_mirror_to_csv_labeled(
    raw_dir: Path,
    out_csv: Path = Path("un_mirror/normalized/energy_obs_labeled.csv"),
    cfg: UNDataConfig = CFG,
) -> None:
    """
    Writes a CSV with Series + Obs attributes plus human-readable labels and scaled values.
    """
    files = sorted(raw_dir.glob("*.xml"))
    _ensure_parent(out_csv)
    if out_csv.exists():
        out_csv.unlink()

    label_maps = build_energy_codelists(cfg)

    rows_written = 0
    for i, f in enumerate(files, start=1):
        df = parse_structurespecific_with_series(f)
        if not df.empty:
            df["__source_file"] = f.name
            df = _enrich_labels_and_numeric(df, label_maps)
            df.to_csv(out_csv, mode="a", header=not out_csv.exists(), index=False)
            rows_written += len(df)
        if i % 100 == 0:
            print(f"csv labeled: processed {i}/{len(files)} files")

    if rows_written == 0:
        raise RuntimeError("No observations parsed; CSV not written.")
    print(f"Wrote {rows_written:,} rows to {out_csv}")

def normalize_mirror_to_parquet_labeled(
    raw_dir: Path,
    out_parquet: Path = Path("un_mirror/normalized/energy_obs_labeled.parquet"),
    cfg: UNDataConfig = CFG,
) -> None:
    """
    Parquet export with Series + Obs attributes, labels, and scaled values.
    """
    files = sorted(raw_dir.glob("*.xml"))
    _ensure_parent(out_parquet)
    label_maps = build_energy_codelists(cfg)

    chunks = []
    for i, f in enumerate(files, start=1):
        df = parse_structurespecific_with_series(f)
        if not df.empty:
            df["__source_file"] = f.name
            df = _enrich_labels_and_numeric(df, label_maps)
            chunks.append(df)
        if i % 100 == 0:
            print(f"parquet labeled: parsed {i}/{len(files)}")

    if not chunks:
        raise RuntimeError("No observations parsed. Keep raw XML and use an SDMX parser library instead.")

    out = pd.concat(chunks, ignore_index=True)
    out.to_parquet(out_parquet, index=False)
    print(f"Wrote {len(out):,} rows to {out_parquet}")

#%% run
# Mirror everything (choose years relevant to you)
# Adjust start/end to match what you want locally (or discover max coverage later).
if __name__ == "__main__":
    # mirror_all_areas(CFG, start_year=1990, end_year=2022, year_window=10, force=False)

    # Then (optional) normalize for fast filtering
    # normalize_mirror_to_parquet(CFG.out_raw_dir)
    # normalize_mirror_to_parquet_labeled(CFG.out_raw_dir)

    # Or (optional) write one big CSV (slower, larger)
    # export_mirror_to_csv(CFG.out_raw_dir, Path("un_mirror/normalized/energy_obs.csv"))
    export_mirror_to_csv_labeled(CFG.out_raw_dir, Path("un_mirror/normalized/energy_obs_labeled.csv"))
#%%
