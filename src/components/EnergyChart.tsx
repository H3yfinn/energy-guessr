import React, { useState } from "react";
import { EnergyProfile, SectorKey, formatEnergy } from "../domain/energy";

const FUEL_COLORS: Record<string, string> = {
  coal: "#1f2933",
  oil: "#b05b1d",
  gas: "#1c7ed6",
  renewables: "#2e8b57",
  renewables_and_others: "#2e8b57",
  electricity: "#7b1fa2",
  elec_gen: "#7b1fa2",
  net_imports: "#0d9488",
  industry: "#4b5563",
  transport: "#f97316",
  buildings: "#eab308",
  non_energy_use: "#db2777",
  others: "#94a3b8",
  other: "#9ca3af",
};

const FUEL_ORDER: Record<string, number> = {
  coal: 0,
  oil: 1,
  gas: 2,
  renewables_and_others: 3,
  renewables: 3,
  other: 4,
  industry: 5,
  transport: 6,
  buildings: 7,
  non_energy_use: 8,
  others: 9,
  electricity: 10,
  elec_gen: 10,
  net_imports: 11,
};

function formatFuelLabel(fuel: string): string {
  return fuel.replace(/_and_/g, " & ").replace(/_/g, " ");
}

interface EnergyChartProps {
  profile: EnergyProfile;
  sectors: SectorKey[];
  year: number;
  scenario: string;
}

const SECTOR_LABELS: Record<string, string> = {
  "07_total_primary_energy_supply": "Total primary energy supply",
  "12_total_final_consumption": "Total final consumption",
  "09_total_transformation_sector": "Total transformation sector",
  "18_electricity_output_in_gwh": "Electricity generation",
  net_imports: "Net imports",
};

export function EnergyChart({
  profile,
  sectors,
  year,
  scenario,
}: EnergyChartProps) {
  const [showImage, setShowImage] = useState(true);

  const chartSectors =
    sectors.length > 0
      ? sectors
      : (Object.keys(profile.sectors) as SectorKey[]);

  const sortFuels = (
    fuels: { fuel: string; value: number }[],
    sector: string
  ) => {
    let filtered = fuels;
    if (sector === "18_electricity_output_in_gwh") {
      filtered = fuels.filter(
        (item) =>
          item.fuel !== "electricity" &&
          item.fuel !== "elec_gen" &&
          item.fuel !== "17_electricity"
      );
    }
    // Ensure electricity shows last in other charts
    return filtered.sort(
      (a, b) => (FUEL_ORDER[a.fuel] ?? 99) - (FUEL_ORDER[b.fuel] ?? 99)
    );
  };

  const { maxValue, minValue } = chartSectors.reduce(
    (acc, sectorKey) => {
      const sectorValues = profile.sectors[sectorKey] ?? [];
      sectorValues.forEach((item) => {
        const numericValue = Number(item.value) || 0;
        acc.maxValue = Math.max(acc.maxValue, numericValue);
        acc.minValue = Math.min(acc.minValue, numericValue);
      });
      return acc;
    },
    { maxValue: 0, minValue: 0 }
  );

  const hasPositive = maxValue > 0;
  const hasNegative = minValue < 0;
  const range =
    hasPositive && hasNegative
      ? maxValue - minValue
      : Math.max(maxValue, Math.abs(minValue)) || 1;
  const baselinePercent =
    hasPositive && hasNegative
      ? (-minValue / (maxValue - minValue)) * 100
      : hasPositive
      ? 0
      : 100;

  return (
    <div className="space-y-4">
      {profile.chartImage && showImage && (
        <img
          className="w-full max-h-96 object-contain border rounded"
          src={`/energy-graphs/${profile.chartImage}`}
          alt={`${profile.name} energy balance`}
          onError={() => setShowImage(false)}
        />
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {chartSectors.map((sectorKey) => {
          const fuels = sortFuels(profile.sectors[sectorKey] ?? [], sectorKey);
          return (
            <div
              key={sectorKey}
              className="border rounded p-3 bg-white dark:bg-slate-800"
            >
              <div className="flex items-baseline mb-2">
                <p className="text-sm font-semibold">
                  {SECTOR_LABELS[sectorKey] ?? sectorKey}
                </p>
              </div>
              {fuels.length === 0 ? (
                <p className="text-xs text-gray-500">No data</p>
              ) : (
                <div
                  className="relative h-48 flex items-end gap-2"
                  style={{ paddingLeft: "36px" }}
                >
                  <div className="absolute left-[30px] top-0 bottom-0 w-px bg-gray-300 dark:bg-slate-600" />
                  <div className="absolute left-0 top-0 text-[10px] text-gray-500 dark:text-gray-400">
                    {formatEnergy(maxValue)}
                  </div>
                  <div className="absolute left-0 bottom-0 text-[10px] text-gray-500 dark:text-gray-400">
                    {formatEnergy(minValue)}
                  </div>
                  <div
                    className="absolute h-px bg-gray-400 dark:bg-slate-500 w-full"
                    style={{ bottom: `${baselinePercent}%`, left: 0 }}
                  />
                  {fuels.map((item) => {
                    const numericValue = Number(item.value) || 0;
                    const heightPercent =
                      (Math.abs(numericValue) / range) * 100;
                    const isPositive = numericValue >= 0;
                    const color = FUEL_COLORS[item.fuel] ?? FUEL_COLORS.other;
                    return (
                      <div key={item.fuel} className="flex-1 h-full relative">
                        <div
                          className="absolute left-1/4 right-1/4 rounded"
                          style={
                            isPositive
                              ? {
                                  height: `${heightPercent}%`,
                                  bottom: `${baselinePercent}%`,
                                  backgroundColor: color,
                                }
                              : {
                                  height: `${heightPercent}%`,
                                  top: `${100 - baselinePercent}%`,
                                  backgroundColor: color,
                                }
                          }
                          title={`${item.fuel}: ${formatEnergy(numericValue)}`}
                        />
                        <p className="text-[10px] mt-1 text-center text-gray-700 dark:text-gray-200 break-words">
                          {formatFuelLabel(item.fuel)}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
