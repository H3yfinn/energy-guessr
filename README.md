# Energy Guessr

Guess the economy by looking at its energy balance charts. The app reads a pre-generated JSON file with all sector/fuel values and optional chart images.

## Quick start (no CSV needed)

1) `npm install`  
2) `npm start`  
3) Open http://localhost:3000 and play.

The app will use `public/data/energy-profiles.json` if present. If it is missing, it falls back to the sample dataset in `public/data/energy-profiles.sample.json`.

## Data pipeline (CSV → JSON)

- The source CSV (`merged_file_energy_ALL_*.csv`) stays local and is ignored by git.
- `scripts/create_energy_assets_csv.py` converts that CSV into `public/data/energy-profiles.json` (the file the app serves).
- When you run `npm start` or `npm run build`, npm automatically runs a matching `prestart`/`prebuild` step first. (These are just npm “hooks”: scripts that run before the main command.) That step calls `scripts/prepare-energy-data.js` to make sure `public/data/energy-profiles.json` exists.
  - If the CSV is present on your machine, it regenerates the JSON (may take ~20–30s).
  - If the CSV is missing (e.g., in GitHub Pages CI or on a machine without the CSV), it just logs a warning and leaves the existing JSON in `public/data/`.
- Commit the generated `public/data/energy-profiles.json` so deployments can run without the CSV.
- Optional: `scripts/create_energy_assets.py` supports Excel inputs and can also emit chart images into `public/energy-graphs/`.

### Regenerate the JSON locally

```bash
python scripts/create_energy_assets_csv.py ^
  --input ./merged_file_energy_ALL_20250814.csv ^
  --output-json ./public/data/energy-profiles.json ^
  --years 2010 2015 2020 2025 2030 2035 2040 2045 2050 2055 2060 ^
  --default-year 2020 ^
  --scenario reference ^
  --label-column economy_name
```

Notes:
- Required columns: `economy`, `sectors`, `scenarios`, `fuels`, and numeric year columns (e.g., `2020`).
- Only selected sectors are kept by default: `07_total_primary_energy_supply`, `12_total_final_consumption`, `09_total_transformation_sector`, `18_electricity_output_in_gwh`, and net imports are derived.
- Uses chunked CSV reads so the large file does not need to fit in memory.

### Deploying (GitHub Pages)

- The workflow in `.github/workflows/deploy.yml` builds and publishes `./build` to `gh-pages` on pushes to `main`. It relies on the committed JSON; the CSV is not needed in CI.
- For an immediate publish from your machine, run `npm run deploy` (uses the local JSON and pushes to `gh-pages`).
- Keep the CSV out of git; only the JSON (and optional chart images) need to be committed for the site to work.

## Game basics

- After you finish a round, the app simply reveals the stats that belong to the economy you guessed—there’s no proximity score or distance-based feedback yet.
- Using **Share** just copies those stats as plain text so you can paste the data for that specific economy (it does not emit Wordle-style colored squares). > would be good to improve in the future.

## Where to edit

- Data: `public/data/energy-profiles.json` (tracked), `public/energy-graphs/` (optional images)
- Types/logic: `src/domain/energy.ts`
- UI: `src/components/EnergyGame.tsx`, `src/components/EnergyChart.tsx`, `src/components/EnergyShare.tsx`

## Credits & License

Adapted from Worldle (MIT). See `LICENSE` for details.
