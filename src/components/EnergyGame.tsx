import React, { useEffect, useMemo, useRef, useState } from "react";
import { DateTime } from "luxon";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import seedrandom from "seedrandom";
import {
  chooseProfile,
  EnergyGuess,
  EnergyProfile,
  findProfile,
  proximityFromDistance,
  sectorTotal,
  totalEnergy,
  netImports,
  netImportsByFuel,
  formatEnergy,
  sanitizeEconomyName,
  FuelValue,
  NAME_ALIASES,
} from "../domain/energy";
import { useEnergyDataset } from "../hooks/useEnergyDataset";
import { useEnergyGuesses } from "../hooks/useEnergyGuesses";
import { startCase } from "lodash-es";
import { EnergyInput } from "./EnergyInput";
import { EnergyChart } from "./EnergyChart";
import { EnergyGuesses } from "./EnergyGuesses";
import { EnergyShare } from "./EnergyShare";
import { SettingsData } from "../hooks/useSettings";
import { SectorKey } from "../domain/energy";
import chartMeta from "../config/chartMeta.json";
import { computeCardSizing } from "../utils/cardSizing";

const MAX_TRY_COUNT = 6;
const WORLD_TILE_COUNT = 10;
const INSTRUCTIONS_KEY_PREFIX = "energy_guessr_instructions_seen_";
const ALIAS_LABELS: Record<string, string> = {
  taiwan: "Taiwan",
  southkorea: "South Korea",
  republicofkorea: "Republic of Korea",
  korea: "Korea",
  unitedstates: "United States",
  usa: "USA",
  us: "US",
  hongkong: "Hong Kong",
  hk: "Hong Kong",
  russia: "Russia",
  chinesetaipei: "Chinese Taipei",
};
const APEC_ECONOMIES_TEXT =
  "Australia, Brunei Darussalam, Canada, Chile, China, Hong Kong (China), Indonesia, Japan, Republic of Korea, Malaysia, Mexico, New Zealand, Papua New Guinea, Peru, Philippines, Russian Federation, Singapore, Chinese Taipei, Thailand, United States, Viet Nam.";

function prettyName(name: string): string {
  if (name === name.toUpperCase()) {
    return name
      .toLowerCase()
      .split(" ")
      .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
      .join(" ");
  }
  return name;
}
type FuelMeta = {
  key: string;
  color: string;
  order: number;
  hide_in_elec_gen?: boolean;
};
const fuelMeta: FuelMeta[] = chartMeta.fuels as FuelMeta[];

function getDayString() {
  return DateTime.now().toFormat("yyyy-MM-dd");
}

function computeGuessMetrics(profile: EnergyProfile) {
  const tfc = sectorTotal(profile, "12_total_final_consumption");
  const production = sectorTotal(profile, "01_production");
  const elecGen = sectorTotal(profile, "18_electricity_output_in_gwh");
  const netImportsValue = netImports(profile);
  return { tfc, production, elecGen, netImports: netImportsValue };
}

interface EnergyGameProps {
  settingsData: SettingsData;
}

export function EnergyGame({ settingsData }: EnergyGameProps) {
  const { t } = useTranslation();
  const dayString = useMemo(getDayString, []);

  const [datasetMode, setDatasetMode] = useState<"apec" | "world">("apec");
  const [pulseMode, setPulseMode] = useState<"apec" | "world" | null>(null);
  const {
    dataset,
    loading,
    error,
    years,
    selectedYear,
    setYear,
    source,
    available,
  } = useEnergyDataset(datasetMode);
  const [targetProfile, setTargetProfile] = useState<EnergyProfile | null>(
    null
  );
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, addGuess, resetGuesses] = useEnergyGuesses(dayString);
  const [tileOptions, setTileOptions] = useState<EnergyProfile[]>([]);
  const [wrongTiles, setWrongTiles] = useState<Set<string>>(new Set());
  const [showInstructions, setShowInstructions] = useState(false);
  const [showGlossary, setShowGlossary] = useState(false);
  const [showHelpBadge, setShowHelpBadge] = useState(true);
  const lastEconomyRef = useRef<string | null>(null);
  const elecHideSet = useMemo(
    () =>
      new Set(
        (chartMeta.fuels as FuelMeta[])
          .filter((f) => f.hide_in_elec_gen)
          .map((f) => f.key)
      ),
    []
  );
  const inputOptions = useMemo(() => {
    if (!dataset) return [];
    const seen = new Set<string>();
    const base: string[] = [];
    dataset.profiles.forEach((profile) => {
      const key = sanitizeEconomyName(profile.name);
      if (seen.has(key)) return;
      seen.add(key);
      base.push(prettyName(profile.name));
    });
    // Add alias entries if the target exists
    Object.entries(NAME_ALIASES).forEach(([alias, target]) => {
      const targets = Array.isArray(target) ? target : [target];
      if (targets.some((t) => seen.has(t))) {
        base.push(ALIAS_LABELS[alias] ?? startCase(alias));
      }
    });
    return Array.from(new Set(base));
  }, [dataset]);
  useEffect(() => {
    const handler = () => setShowInstructions(true);
    window.addEventListener("energy-show-help", handler);
    return () => window.removeEventListener("energy-show-help", handler);
  }, []);
  useEffect(() => {
    const handler = () => setShowGlossary(true);
    window.addEventListener("energy-show-glossary", handler);
    return () => window.removeEventListener("energy-show-glossary", handler);
  }, []);

  useEffect(() => {
    if (!dataset) return;
    let nextProfile: EnergyProfile | null = null;

    // Keep the current country when switching years/datasets if available
    if (targetProfile) {
      nextProfile =
        dataset.profiles.find(
          (p) =>
            p.economy === targetProfile.economy ||
            sanitizeEconomyName(p.name) ===
              sanitizeEconomyName(targetProfile.name)
        ) ?? null;
    }

    // Fallback to last stored economy (World mode)
    if (!nextProfile && datasetMode === "world" && lastEconomyRef.current) {
      nextProfile =
        dataset.profiles.find((p) => p.economy === lastEconomyRef.current) ??
        null;
    }

    // Final fallback: daily seed
    if (!nextProfile) {
      nextProfile = chooseProfile(dataset, dayString);
    }

    setTargetProfile(nextProfile);
    lastEconomyRef.current = nextProfile?.economy ?? lastEconomyRef.current;
  }, [dataset, datasetMode, dayString, targetProfile]);

  // Show instructions when switching datasets (first time only per dataset)
  useEffect(() => {
    const key = `${INSTRUCTIONS_KEY_PREFIX}${datasetMode}`;
    const seen = localStorage.getItem(key);
    if (!seen) {
      setShowInstructions(true);
      localStorage.setItem(key, "1");
      setShowHelpBadge(true);
    } else {
      setShowInstructions(false);
      setShowHelpBadge(false);
    }
  }, [datasetMode]);

  // Build tile options (World mode only)
  useEffect(() => {
    if (datasetMode !== "world" || !dataset || !targetProfile) {
      setTileOptions([]);
      setWrongTiles(new Set());
      return;
    }
    const rng = seedrandom(`${dayString}:${targetProfile.economy}`);
    const pool = dataset.profiles
      .filter((p) => p.economy !== targetProfile.economy)
      .sort((a, b) => a.economy.localeCompare(b.economy));
    // Deterministic shuffle
    for (let i = pool.length - 1; i > 0; i -= 1) {
      const j = Math.floor(rng() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    const others = pool.slice(0, WORLD_TILE_COUNT - 1);
    const combined = [...others, targetProfile].sort((a, b) =>
      a.economy.localeCompare(b.economy)
    );
    setTileOptions(combined);
    setWrongTiles(new Set());
  }, [dataset, datasetMode, targetProfile, dayString]);

  const profileLookup = useMemo(() => {
    if (!dataset) return new Map<string, EnergyProfile>();
    const map = new Map<string, EnergyProfile>();
    dataset.profiles.forEach((profile) => {
      map.set(sanitizeEconomyName(profile.name), profile);
    });
    return map;
  }, [dataset]);

  const displayGuesses = useMemo(() => {
    if (!dataset) return guesses;
    return guesses.map((guess) => {
      const profile = profileLookup.get(sanitizeEconomyName(guess.name));
      if (!profile) return guess;
      const metrics = computeGuessMetrics(profile);
      return { ...guess, ...metrics, name: prettyName(profile.name) };
    });
  }, [dataset, guesses, profileLookup]);

  const maxTries =
    datasetMode === "world" ? Number.MAX_SAFE_INTEGER : MAX_TRY_COUNT;
  const gameEnded =
    guesses.length >= maxTries ||
    guesses[guesses.length - 1]?.proximity === 100;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    handleGuess(currentGuess);
  };

  const handleGuess = (guessValue: string) => {
    if (!dataset || !targetProfile) {
      toast.error("Dataset not ready yet.");
      return;
    }

    const guessedProfile = findProfile(dataset, guessValue);
    if (guessedProfile == null) {
      toast.error(t("unknownCountry"));
      return;
    }

    const targetTotal = totalEnergy(targetProfile);
    const datasetTotals = dataset.profiles.map((p) => totalEnergy(p));
    const maxTotal = Math.max(...datasetTotals, targetTotal);
    const minTotal = Math.min(...datasetTotals, targetTotal);
    const totalRange = Math.max(maxTotal - minTotal, 1);

    const guessedTotal = totalEnergy(guessedProfile);
    const totalDiff = Math.abs(guessedTotal - targetTotal);
    const isExactMatch =
      sanitizeEconomyName(guessedProfile.name) ===
      sanitizeEconomyName(targetProfile.name);
    const proximityRaw = proximityFromDistance(totalDiff, totalRange);
    const proximity = isExactMatch ? 100 : Math.min(proximityRaw, 99);

    const guessedMetrics = computeGuessMetrics(guessedProfile);

    const newGuess: EnergyGuess = {
      name: guessedProfile.name,
      distance: totalDiff,
      proximity,
      total: guessedTotal,
      totalProximity: proximity,
      production: guessedMetrics.production,
      tfc: guessedMetrics.tfc,
      elecGen: guessedMetrics.elecGen,
      netImports: guessedMetrics.netImports,
    };

    addGuess(newGuess);
    setCurrentGuess("");

    if (proximity === 100) {
      toast.success(t("welldone"), { delay: 2000 });
    } else if (datasetMode === "world") {
      // mark tile as wrong
      setWrongTiles((prev) => {
        const next = new Set(prev);
        next.add(guessedProfile.economy);
        return next;
      });
    }
  };

  const sectorLabels = useMemo<Record<string, string>>(
    () => ({
      "01_production": "Production",
      "12_total_final_consumption": "Total final consumption",
      "09_total_transformation_sector": "Total transformation sector",
      "18_electricity_output_in_gwh": "Electricity generation",
      "02_imports": "Imports",
      "03_exports": "Exports",
      net_imports: "Net imports",
    }),
    []
  );

  const displaySectors: SectorKey[] = useMemo(
    () => [
      "12_total_final_consumption",
      "01_production",
      "18_electricity_output_in_gwh",
      "net_imports",
    ],
    []
  );

  const profileForDisplay = useMemo(() => {
    if (!targetProfile) return null;
    const elecGenFuels =
      targetProfile.sectors["18_electricity_output_in_gwh"] ?? [];
    const netImportFuels = netImportsByFuel(targetProfile);
    return {
      ...targetProfile,
      sectors: {
        ...targetProfile.sectors,
        "18_electricity_output_in_gwh":
          elecGenFuels.length > 0
            ? elecGenFuels
            : [
                {
                  fuel: "electricity",
                  value: sectorTotal(
                    targetProfile,
                    "18_electricity_output_in_gwh"
                  ),
                },
              ],
        net_imports:
          netImportFuels.length > 0
            ? netImportFuels
            : [
                {
                  fuel: "net_imports",
                  value: netImports(targetProfile),
                },
              ],
      },
    };
  }, [targetProfile]);

  const currentYear = dataset?.year;

  useEffect(() => {
    if (!profileForDisplay || !currentYear) return;
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.debug("[energy] profile", {
        year: currentYear,
        sectors: Object.keys(profileForDisplay.sectors),
        production: sectorTotal(profileForDisplay, "01_production"),
        tfc: sectorTotal(profileForDisplay, "12_total_final_consumption"),
        elec: sectorTotal(profileForDisplay, "18_electricity_output_in_gwh"),
        net: sectorTotal(profileForDisplay, "net_imports"),
      });
    }
  }, [currentYear, profileForDisplay]);

  const sectorTotals = useMemo(() => {
    if (!profileForDisplay) return [];
    const order: SectorKey[] = [
      "12_total_final_consumption",
      "01_production",
      "net_imports",
      "18_electricity_output_in_gwh",
    ];
    return order
      .filter((k) => displaySectors.includes(k))
      .map((sectorKey) => {
        const total = sectorTotal(profileForDisplay, sectorKey);
        return {
          key: sectorKey,
          label: sectorLabels[sectorKey] ?? sectorKey,
          total,
        };
      });
  }, [displaySectors, profileForDisplay, sectorLabels]);

  if (loading || !dataset || !profileForDisplay) {
    return <p className="p-4 text-center">Loading energy balances...</p>;
  }

  return (
    <div className="flex-grow flex flex-col mx-2">
      {error && (
        <div className="bg-amber-100 border border-amber-300 text-amber-800 p-2 mb-2 text-sm">
          {error} - using sample data.
        </div>
      )}
      <div className="flex gap-4 items-center mb-2 flex-wrap justify-between">
        <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
          <span className="font-semibold">Year:</span>
          {years.length > 1 && (
            <div className="flex items-center gap-2">
              {years.length <= 3 ? (
                <div className="flex gap-1">
                  {years.map((y) => (
                    <button
                      key={y}
                      type="button"
                      className={`px-2 py-1 rounded border text-xs ${
                        (selectedYear ?? dataset.year) === y
                          ? "bg-blue-100 text-blue-800 border-blue-300 dark:bg-slate-700 dark:text-blue-100 dark:border-blue-500"
                          : "bg-white text-gray-700 border-gray-200 dark:bg-slate-800 dark:text-gray-200 dark:border-slate-700"
                      }`}
                      onClick={() => {
                        setYear(
                          y,
                          datasetMode === "world"
                            ? targetProfile?.economy
                            : undefined
                        );
                      }}
                    >
                      {y}
                    </button>
                  ))}
                </div>
              ) : (
                <>
                  <input
                    type="range"
                    min={years[0]}
                    max={years[years.length - 1]}
                    step={5}
                    value={selectedYear ?? dataset.year}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      const closest = years.reduce((prev, curr) =>
                        Math.abs(curr - val) < Math.abs(prev - val)
                          ? curr
                          : prev
                      );
                      setYear(
                        closest,
                        datasetMode === "world"
                          ? targetProfile?.economy
                          : undefined
                      );
                    }}
                  />
                  <span className="text-[11px] text-gray-500 flex items-center gap-1">
                    {years.map((y) => (
                      <span key={y} className="flex items-center gap-1">
                        {(selectedYear ?? dataset.year) === y ? (
                          <span className="font-bold text-black dark:text-white">
                            {y}
                          </span>
                        ) : (
                          <span>{y}</span>
                        )}
                        {y !== years[years.length - 1] && <span>•</span>}
                      </span>
                    ))}
                  </span>
                </>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 flex-wrap ml-auto">
          {available.apec && available.world && (
            <div className="flex items-center gap-3 text-xs">
              <span className="font-semibold">Dataset:</span>
              <button
                type="button"
                className={`border px-2 py-1 rounded transition ${
                  datasetMode === "apec"
                    ? "bg-blue-50 border-blue-200 dark:bg-slate-800"
                    : "hover:bg-gray-50 dark:hover:bg-slate-800"
                } ${pulseMode === "apec" ? "animate-pulse" : ""}`}
                onClick={() => {
                  setDatasetMode("apec");
                  resetGuesses();
                  setTargetProfile(null);
                  setPulseMode("apec");
                  setTimeout(() => setPulseMode(null), 1500);
                  toast.info("🏳 Switched to APEC dataset", {
                    autoClose: 2500,
                    position: "top-center",
                    closeOnClick: true,
                  });
                }}
              >
                APEC
              </button>
              <button
                type="button"
                className={`border px-2 py-1 rounded transition ${
                  datasetMode === "world"
                    ? "bg-blue-50 border-blue-200 dark:bg-slate-800"
                    : "hover:bg-gray-50 dark:hover:bg-slate-800"
                } ${pulseMode === "world" ? "animate-pulse" : ""}`}
                onClick={() => {
                  setDatasetMode("world");
                  resetGuesses();
                  setTargetProfile(null);
                  setPulseMode("world");
                  setTimeout(() => setPulseMode(null), 1500);
                  toast.info("🌐 Switched to World dataset (UN)", {
                    autoClose: 2500,
                    position: "top-center",
                    closeOnClick: true,
                  });
                }}
              >
                World
              </button>
              <span className="text-xs font-semibold px-2 py-1 rounded bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200">
                Source: {source === "world" ? "World (UN/EI)" : "APEC"}
              </span>
            </div>
          )}
          {showHelpBadge && (
            <button
              className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
              type="button"
              onClick={() => {
                setShowInstructions(true);
                setShowHelpBadge(false);
              }}
            >
              Show help
            </button>
          )}
          <button
            className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
            type="button"
            onClick={() => {
              resetGuesses();
              const randomSeed = dayString + "-" + Date.now();
              const next = chooseProfile(dataset, randomSeed);
              setTargetProfile(next);
              lastEconomyRef.current = next.economy;
            }}
          >
            Change country
          </button>
        </div>
      </div>
      <div className="my-1">
        <EnergyChart
          profile={profileForDisplay ?? targetProfile}
          sectors={displaySectors}
          year={dataset.year}
          scenario={dataset.scenario}
          source={datasetMode === "world" ? "world" : "apec"}
        />
      </div>
      <div
        className="grid gap-2 text-center text-sm my-2"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}
      >
        {sectorTotals.map((sector) => {
          const fuels =
            (profileForDisplay.sectors as Record<string, FuelValue[]>)[
              sector.key
            ] ?? [];
          const visibleFuels =
            sector.key === "18_electricity_output_in_gwh"
              ? fuels.filter((f) => !elecHideSet.has(f.fuel))
              : fuels;
          const barCount = Math.max(1, visibleFuels.length);
          const sizing = computeCardSizing(barCount, sector.key);
          return (
            <div
              key={sector.key}
              className="border rounded p-2 bg-white dark:bg-slate-800"
              style={{
                gridColumn: `span ${sizing.span} / span ${sizing.span}`,
                minWidth: `${sizing.minWidth}px`,
              }}
            >
              <div className="font-semibold">{sector.label}</div>
              <div className="text-lg">{formatEnergy(sector.total)}</div>
            </div>
          );
        })}
      </div>
      <EnergyGuesses
        rowCount={MAX_TRY_COUNT}
        guesses={displayGuesses}
        hideTable={datasetMode === "world"}
        compact={datasetMode === "apec"}
      />
      {showInstructions && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded shadow-lg max-w-lg w-full p-4 border dark:border-slate-700">
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-lg font-semibold">How to play</h3>
              <button
                className="text-sm px-2 py-1 border rounded"
                onClick={() => setShowInstructions(false)}
              >
                Close
              </button>
            </div>
            {datasetMode === "world" ? (
              <ul className="list-disc pl-5 text-sm space-y-1">
                <li>Click one of the 10 country tiles to guess.</li>
                <li>
                  Wrong guesses turn red and are crossed out; you get unlimited
                  attempts.
                </li>
                <li>
                  Charts show the selected economy&apos;s energy balance for the
                  chosen year.
                </li>
              </ul>
            ) : (
              <ul className="list-disc pl-5 text-sm space-y-1">
                <li>Type the country name and press Guess.</li>
                <li>You have 5 guesses; aim for an exact match.</li>
                <li>
                  Use the year controls to switch context. Use “Change country”
                  or switch dataset to try a new country.
                </li>
              </ul>
            )}
          </div>
        </div>
      )}
      {showGlossary && (
        <div className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded shadow-lg max-w-lg w-full p-4 border dark:border-slate-700">
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-lg font-semibold">Glossary</h3>
              <button
                className="text-sm px-2 py-1 border rounded"
                onClick={() => setShowGlossary(false)}
              >
                Close
              </button>
            </div>
            {/* prettier-ignore */}
            <ul className="list-disc pl-5 text-sm space-y-1">
              <li>
                <strong>TFC</strong>: Total Final Consumption (energy used by end users:
                industry, transport, buildings, others). “Others” covers non-specified uses,
                agriculture, and similar categories.
              </li>
              <li>
                <strong>Production</strong>: Energy produced from primary sources (coal, oil,
                gas, renewables), excluding electricity output, refined products and other
                forms of energy transformation.
              </li>
              <li>
                <strong>Net imports</strong>: Imports minus exports (does not count
                international transport as exports).
              </li>
              <li>
                <strong>Electricity generation</strong>: Shows generation output. World uses
                Energy Institute data. Ren. &amp; Others covers other renewable sources (e.g.,
                biomass) as well as other sources such as non-specified.
              </li>
              <li>
                <strong>Units</strong>: All values have been converted to PJ/EJ for better
                comparison (1 EJ = 1,000 PJ).
              </li>
            </ul>
          </div>
        </div>
      )}
      <div className="my-2">
        {datasetMode === "world" ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {tileOptions.map((opt) => {
              const isWrong = wrongTiles.has(opt.economy);
              const isCorrect =
                guesses[guesses.length - 1]?.name === opt.name &&
                guesses[guesses.length - 1]?.proximity === 100;
              const tfcValue = sectorTotal(opt, "12_total_final_consumption");
              const flashClass = isCorrect
                ? "guess-flash-correct"
                : isWrong
                ? "guess-flash-wrong"
                : "";
              return (
                <button
                  key={opt.economy}
                  type="button"
                  className={`border rounded p-2 text-sm text-left transition ${flashClass} ${
                    isCorrect
                      ? "bg-green-100 border-green-300 text-green-900"
                      : isWrong
                      ? "bg-red-50 border-red-200 text-red-700 line-through"
                      : "bg-white dark:bg-slate-800 hover:bg-gray-50 dark:hover:bg-slate-700"
                  }`}
                  onClick={() => handleGuess(opt.name)}
                >
                  <div className="flex flex-col gap-0.5">
                    <span>{opt.name}</span>
                    {isWrong && (
                      <span className="text-[11px] font-semibold text-gray-700 dark:text-gray-200 line-through decoration-red-500">
                        {formatEnergy(tfcValue)} (Total final consumption)
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        ) : gameEnded ? (
          <EnergyShare
            guesses={displayGuesses}
            dayString={dayString}
            theme={settingsData.theme}
          />
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="flex flex-col">
              <EnergyInput
                currentGuess={currentGuess}
                setCurrentGuess={setCurrentGuess}
                options={inputOptions}
              />
              <button
                className="border-2 uppercase my-0.5 hover:bg-gray-50 active:bg-gray-100 dark:hover:bg-slate-800 dark:active:bg-slate-700"
                type="submit"
              >
                {t("guess")}
              </button>
            </div>
          </form>
        )}
      </div>
      {datasetMode === "apec" && (
        <div className="text-xs text-gray-600 dark:text-gray-300 mt-3">
          <strong>APEC economies:</strong>
          <span> {" " + APEC_ECONOMIES_TEXT}</span>
        </div>
      )}
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
        <span>
          APEC data is based on{" "}
          <a
            className="underline"
            href="https://aperc.or.jp/reports/outlook.php"
            target="_blank"
            rel="noreferrer"
          >
            APERC 9th Energy Outlook (2025) Reference scenario
          </a>
          . UN data is from the{" "}
          <a
            className="underline"
            href="https://unstats.un.org/unsd/energystats/api/"
            target="_blank"
            rel="noreferrer"
          >
            UNSD API
          </a>
          . Electricity by fuel (2023) is from the Energy Institute Statistical
          Review (
          <a
            className="underline"
            href="https://www.energyinst.org/statistical-review/resources-and-data-downloads"
            target="_blank"
            rel="noreferrer"
          >
            data download
          </a>
          ).
        </span>
      </div>
    </div>
  );
}
