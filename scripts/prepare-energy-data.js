/**
 * Run the CSV -> JSON energy data conversion on startup.
 *
 * This keeps the large source file local and regenerates the app's
 * `public/data/energy-profiles-apec.json` before `npm start` / `npm run build`.
 *
 * It is intentionally forgiving: if the CSV or Python is missing, it will
 * log a warning and continue so dev server still launches.
 */
const { existsSync, statSync } = require("fs");
const { spawnSync } = require("child_process");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const inputCsv = path.resolve(
  projectRoot,
  "merged_file_energy_ALL_20250814.csv"
);
const outputJson = path.resolve(
  projectRoot,
  "public",
  "data",
  "energy-profiles-apec.json"
);
const scriptPath = path.resolve(
  projectRoot,
  "scripts",
  "create_energy_assets_csv.py"
);

function log(msg) {
  // eslint-disable-next-line no-console
  console.log(`[energy-prepare] ${msg}`);
}

// Allow opting out via environment variable
if (process.env.SKIP_ENERGY_PREP === "1" || process.env.SKIP_ENERGY_PREP === "true") {
  log("SKIP_ENERGY_PREP set; skipping data generation.");
  process.exit(0);
}

function run() {
  if (!existsSync(inputCsv)) {
    log(
      `Input CSV not found (${inputCsv}); skipping data generation and keeping existing JSON.`
    );
    return;
  }

  if (!existsSync(scriptPath)) {
    log(
      `Generator script missing (${scriptPath}); skipping data generation.`
    );
    return;
  }

const args = [
  scriptPath,
  "--input",
  inputCsv,
  "--output-json",
  outputJson,
  "--years",
  "2010",
  "2015",
  "2020",
  "2025",
  "2030",
  "2035",
  "2040",
  "2045",
  "2050",
  "2055",
  "2060",
  "--default-year",
  "2020",
  "--scenario",
  "reference",
  "--label-column",
  "economy_name",
];

  const start = Date.now();
  const tryPython = (cmd) =>
    spawnSync(cmd, args, { cwd: projectRoot, stdio: "inherit" });

  log(`Running data prep: py ${args.join(" ")}`);
  let result = tryPython("py");

  if (result.error || result.status !== 0) {
    log(
      `py invocation failed (status ${result.status}, error ${result.error?.message ?? "n/a"}); trying "python".`
    );
    result = tryPython("python");
  }

  if (result.error) {
    log(
      `Python failed to run (${result.error.message}); JSON not regenerated.`
    );
    return;
  }

  if (result.status !== 0) {
    log(
      `Generator exited with code ${result.status}; keeping existing JSON if any.`
    );
    return;
  }

  if (existsSync(outputJson)) {
    const elapsed = ((Date.now() - start) / 1000).toFixed(2);
    const sizeKb = (statSync(outputJson).size / 1024).toFixed(1);
    log(`Generated ${outputJson} in ${elapsed}s (${sizeKb} KB).`);
  } else {
    log("Generator reported success but output file not found.");
  }
}

run();
