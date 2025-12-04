import React, { useEffect, useMemo, useState } from "react";
import { DateTime } from "luxon";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
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
  FuelValue,
} from "../domain/energy";
import { useEnergyDataset } from "../hooks/useEnergyDataset";
import { useEnergyGuesses } from "../hooks/useEnergyGuesses";
import { EnergyInput } from "./EnergyInput";
import { EnergyChart } from "./EnergyChart";
import { EnergyGuesses } from "./EnergyGuesses";
import { EnergyShare } from "./EnergyShare";
import { SettingsData } from "../hooks/useSettings";
import { SectorKey } from "../domain/energy";

const MAX_TRY_COUNT = 6;
const FUEL_LEGEND_COLORS: Record<string, string> = {
  coal: "#1f2933",
  oil: "#b05b1d",
  gas: "#1c7ed6",
  renewables: "#2e8b57",
  renewables_and_others: "#2e8b57",
  electricity: "#7b1fa2",
  other: "#9ca3af",
  industry: "#4b5563",
  transport: "#f97316",
  buildings: "#eab308",
  others: "#94a3b8",
  non_energy_use: "#db2777",
  net_imports: "#0d9488",
};

function getDayString() {
  return DateTime.now().toFormat("yyyy-MM-dd");
}

interface EnergyGameProps {
  settingsData: SettingsData;
}

export function EnergyGame({ settingsData }: EnergyGameProps) {
  const { t } = useTranslation();
  const dayString = useMemo(getDayString, []);

  const { dataset, loading, error, years, selectedYear, setYear } =
    useEnergyDataset();
  const [targetProfile, setTargetProfile] = useState<EnergyProfile | null>(
    null
  );
  const [currentGuess, setCurrentGuess] = useState("");
  const [guesses, addGuess, resetGuesses] = useEnergyGuesses(dayString);

  useEffect(() => {
    if (dataset) {
      setTargetProfile(chooseProfile(dataset, dayString));
    }
  }, [dataset, dayString]);

  const gameEnded =
    guesses.length === MAX_TRY_COUNT ||
    guesses[guesses.length - 1]?.proximity === 100;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!dataset || !targetProfile) {
      toast.error("Dataset not ready yet.");
      return;
    }

    const guessedProfile = findProfile(dataset, currentGuess);
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
    const proximity = proximityFromDistance(totalDiff, totalRange);

    const guessedTPES = sectorTotal(
      guessedProfile,
      "07_total_primary_energy_supply"
    );
    const guessedTFC = sectorTotal(
      guessedProfile,
      "12_total_final_consumption"
    );
    const guessedElecGen = sectorTotal(
      guessedProfile,
      "18_electricity_output_in_gwh"
    );
    const guessedNetImports = netImports(guessedProfile);

    const newGuess: EnergyGuess = {
      name: guessedProfile.name,
      distance: totalDiff,
      proximity,
      total: guessedTotal,
      totalProximity: proximity,
      tpes: guessedTPES,
      tfc: guessedTFC,
      elecGen: guessedElecGen,
      netImports: guessedNetImports,
    };

    addGuess(newGuess);
    setCurrentGuess("");

    if (proximity === 100) {
      toast.success(t("welldone"), { delay: 2000 });
    }
  };

  useEffect(() => {
    if (
      targetProfile &&
      guesses.length === MAX_TRY_COUNT &&
      guesses[guesses.length - 1]?.proximity !== 100
    ) {
      toast.info(targetProfile.name.toUpperCase(), {
        autoClose: false,
        delay: 2000,
      });
    }
  }, [guesses, targetProfile]);

  const sectorLabels = useMemo<Record<string, string>>(
    () => ({
      "07_total_primary_energy_supply": "Total primary energy supply",
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
      "07_total_primary_energy_supply",
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
        tpes: sectorTotal(profileForDisplay, "07_total_primary_energy_supply"),
        tfc: sectorTotal(profileForDisplay, "12_total_final_consumption"),
        elec: sectorTotal(profileForDisplay, "18_electricity_output_in_gwh"),
        net: sectorTotal(profileForDisplay, "net_imports"),
      });
    }
  }, [currentYear, profileForDisplay]);

  const legend = useMemo(() => {
    if (!profileForDisplay) {
      return { sector: [] as string[], fuel: [] as string[] };
    }
    const seen = new Set<string>();
    const sectorMap = profileForDisplay.sectors as Record<string, FuelValue[]>;
    displaySectors.forEach((sector) => {
      (sectorMap[sector] || []).forEach((f) => seen.add(f.fuel));
    });
    const sectorOrder = [
      "industry",
      "transport",
      "buildings",
      "others",
      "non_energy_use",
    ];
    const fuelOrder = [
      "coal",
      "oil",
      "gas",
      "renewables",
      "renewables_and_others",
      "electricity",
      "net_imports",
      "other",
    ];
    const sectorLegend = sectorOrder.filter((f) => seen.has(f));
    const fuelLegend = fuelOrder.filter((f) => seen.has(f));
    return { sector: sectorLegend, fuel: fuelLegend };
  }, [displaySectors, profileForDisplay]);

  const sectorTotals = useMemo(() => {
    if (!profileForDisplay) return [];
    return displaySectors.map((sectorKey) => {
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
      <div className="flex gap-4 items-center mb-2 flex-wrap">
        <button
          className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
          type="button"
          onClick={() => {
            resetGuesses();
            setTargetProfile(chooseProfile(dataset, dayString));
          }}
        >
          Reset today
        </button>
        <button
          className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
          type="button"
          onClick={() => {
            resetGuesses();
            const randomSeed = dayString + "-" + Date.now();
            setTargetProfile(chooseProfile(dataset, randomSeed));
          }}
        >
          Change economy
        </button>
        <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
          <span>Year:</span>
          <span className="font-semibold">{selectedYear ?? dataset.year}</span>
          {years.length > 1 && (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={years[0]}
                max={years[years.length - 1]}
                step={5}
                value={selectedYear ?? dataset.year}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  const closest = years.reduce((prev, curr) =>
                    Math.abs(curr - val) < Math.abs(prev - val) ? curr : prev
                  );
                  resetGuesses();
                  setTargetProfile(null);
                  setYear(closest);
                }}
              />
              <span className="text-[11px] text-gray-500">
                {years.join(" • ")}
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="my-1">
        <EnergyChart
          profile={profileForDisplay ?? targetProfile}
          sectors={displaySectors}
          year={dataset.year}
          scenario={dataset.scenario}
        />
      </div>
      <div className="grid grid-cols-4 gap-2 text-center text-sm my-2">
        {sectorTotals.map((sector) => (
          <div
            key={sector.key}
            className="border rounded p-2 bg-white dark:bg-slate-800"
          >
            <div className="font-semibold">{sector.label}</div>
            <div className="text-lg">{formatEnergy(sector.total)}</div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-4 items-center text-sm text-gray-700 dark:text-gray-200 my-2">
        {legend.sector.map((fuel) => (
          <div key={fuel} className="flex items-center gap-2">
            <span
              className="inline-block w-4 h-4 rounded"
              style={{ backgroundColor: FUEL_LEGEND_COLORS[fuel] || "#666" }}
            />
            <span className="capitalize">{fuel.replace(/_/g, " ")}</span>
          </div>
        ))}
        {legend.sector.length > 0 && legend.fuel.length > 0 && (
          <span className="text-gray-400">|</span>
        )}
        {legend.fuel.map((fuel) => (
          <div key={fuel} className="flex items-center gap-2">
            <span
              className="inline-block w-4 h-4 rounded"
              style={{ backgroundColor: FUEL_LEGEND_COLORS[fuel] || "#666" }}
            />
            <span className="capitalize">{fuel.replace(/_/g, " ")}</span>
          </div>
        ))}
      </div>
      <EnergyGuesses rowCount={MAX_TRY_COUNT} guesses={guesses} />
      <div className="my-2">
        {gameEnded ? (
          <EnergyShare
            guesses={guesses}
            dayString={dayString}
            theme={settingsData.theme}
          />
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="flex flex-col">
              <EnergyInput
                currentGuess={currentGuess}
                setCurrentGuess={setCurrentGuess}
                options={dataset.profiles.map((profile) =>
                  profile.name.toUpperCase()
                )}
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
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
        The calculation for net imports does not consider energy used for
        international transport as exports. Note: 1 EJ = 1,000 PJ.
      </div>
    </div>
  );
}
