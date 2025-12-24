# Energy Guessr

Guess the economy by looking at its energy balance charts. The app reads a pre-generated JSON file with all sector/fuel values and optional chart images.

## Quick start (no CSV needed)

1) `npm install`  
2) `npm start`  
3) Open http://localhost:3000 and play.

The app will use `public/data/energy-profiles-apec.json` (or `energy-profiles-un.json` when you switch to World). If an APEC file is missing, it falls back to the sample dataset in `public/data/energy-profiles.sample.json`.

## Data pipeline (APEC + UN)

- There are two datasets:
  - **APEC** (existing CSV/Excel source) → `public/data/energy-profiles-apec.json`.
  - **World/UN** (mirrored SDMX data) → `public/data/energy-profiles-un.json` (multi-year, e.g., 2010 & 2020).
- Both are generated manually (no prestart/prebuild hooks). You should run the prep scripts before starting/building if you want fresh data.

### JSON structure (APEC & UN)

- Top-level (multi-year): `{ years: [..], defaultYear: 2020, scenario: "reference", datasets: { "2020": { year, scenario, profiles: [...] }, ... } }`.
- Each profile: `{ economy, name, source, metrics, sectors }`.
  - `metrics`: `{ tpes, tfc, elec_gen, net_imports, net_imports_by_fuel: [{fuel,value},...] }`.
  - `sectors` (only what the app charts):
    - `07_total_primary_energy_supply`: by fuel.
    - `12_total_final_consumption`: single `{fuel:"tfc", value:<total>}` entry.
    - `18_electricity_output_in_gwh`: by fuel (APEC = output, UN = transformation inputs).
    - `net_imports`: by fuel (total in metrics).

### UN mirror + prep (world data)

1) Mirror UN energy SDMX data (runs HTTP downloads; may take time):
   ```bash
   python scripts/download_UN_data.py  # mirrors raw XML slices
   ```
2) Export labeled data with conversions and PJ values:
   ```bash
   # in a notebook or shell
   from scripts.download_UN_data import export_mirror_to_csv_labeled, CFG
   export_mirror_to_csv_labeled(CFG.out_raw_dir, Path("scripts/un_mirror/normalized/energy_obs_labeled.csv"))
   ```
3) Build the world JSON (multi-year, default 2010 & 2020):
   ```bash
   python scripts/run_energy_prep.py --un-input scripts/un_mirror/normalized/energy_obs_labeled.csv
   # outputs public/data/energy-profiles-un.json
   ```

### APEC prep (CSV/Excel → JSON)

- One-shot (CSV or Excel):
  ```bash
  python scripts/run_energy_prep.py --apec-input merged_file_energy_ALL_20250814.csv --skip-charts
  # or: --apec-input data/apec_energy.xlsx
  ```

### One-shot prep for both (APEC + UN)

Use the helper wrapper (no npm hooks):
```bash
  python scripts/run_energy_prep.py \
    --apec-input data/apec_energy.xlsx \
    --un-input scripts/un_mirror/normalized/energy_obs_labeled.csv \
    --output-json public/data/energy-profiles-apec.json \
    --un-output-json public/data/energy-profiles-un.json \
    --un-years 2010 2020 \
    --skip-charts
```

Notes:
- Required columns for APEC CSV: `economy`, `sectors`, `scenarios`, `fuels`, numeric year columns (e.g., `2020`).
- UN prep relies on `VALUE_PJ` from the labeled exporter; exports are negative; net_imports are computed.
- Keep raw CSV/XML out of git; commit the generated JSONs.

### Deploying (GitHub Pages)

- The workflow in `.github/workflows/deploy.yml` builds and publishes `./build` to `gh-pages` on pushes to `main`. It relies on the committed JSON; the CSV is not needed in CI.
- For an immediate publish from your machine, run `npm run deploy` (uses the local JSON and pushes to `gh-pages`).
- Keep the CSV out of git; only the JSON (and optional chart images) need to be committed for the site to work.

## Game basics

- After you finish a round, the app simply reveals the stats that belong to the economy you guessed—there’s no proximity score or distance-based feedback yet.
- Using **Share** just copies those stats as plain text so you can paste the data for that specific economy (it does not emit Wordle-style colored squares). > would be good to improve in the future.

## Where to edit

- Data: `public/data/energy-profiles-apec.json` (tracked), `public/data/energy-profiles-un.json` (tracked), `public/energy-graphs/` (optional images)
- Types/logic: `src/domain/energy.ts`
- UI: `src/components/EnergyGame.tsx`, `src/components/EnergyChart.tsx`, `src/components/EnergyShare.tsx`

## Credits & License

Energy Guessr is a fork of Worldle by markgalassi and teuteuf (MIT) – original repo: https://github.com/markgalassi/worldle. Changes © 2025 finn.
