import React, { useMemo, useState } from "react";
import chartMeta from "../config/chartMeta.json";
import { EnergyProfile, SectorKey, formatEnergy } from "../domain/energy";
import { computeCardSizing } from "../utils/cardSizing";

type Theme = "light" | "dark";
type FuelMeta = {
  key: string;
  color: string;
  order: number;
  hide_in_elec_gen?: boolean;
};
const fuelMeta: FuelMeta[] = chartMeta.fuels as FuelMeta[];
const FUEL_COLORS_LIGHT = fuelMeta.reduce<Record<string, string>>((acc, f) => {
  acc[f.key] = f.color;
  return acc;
}, {});
const FUEL_COLORS_DARK: Record<string, string> = {
  ...FUEL_COLORS_LIGHT,
  coal: "#6b7280",
};
const FUEL_ORDER = fuelMeta.reduce<Record<string, number>>((acc, f) => {
  acc[f.key] = f.order;
  return acc;
}, {});

function formatFuelLabel(fuel: string): string {
  if (fuel === "renewables_and_others") return "Others";
  if (fuel === "wind_solar") return "Wind & Solar";
  const normalized = fuel.replace(/_and_/g, " & ").replace(/_/g, " ");
  const parts = normalized.split(" ").filter(Boolean);
  return parts
    .map((part) => {
      if (part === "&") return "&";
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(" ");
}

interface EnergyChartProps {
  profile: EnergyProfile;
  sectors: SectorKey[];
  year: number;
  scenario: string;
  source?: "apec" | "world" | string;
  theme: Theme;
}

const SECTOR_LABELS: Record<string, string> = {
  "01_production": "Production",
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
  source,
  theme,
}: EnergyChartProps) {
  const [showImage, setShowImage] = useState(true);
  const fuelColors = theme === "dark" ? FUEL_COLORS_DARK : FUEL_COLORS_LIGHT;
  const chartSectors = (
    sectors.length > 0 ? sectors : (Object.keys(profile.sectors) as SectorKey[])
  ).sort((a, b) => {
    // Keep Electricity generation at the right end for clarity
    const isElec = (key: string) => key === "18_electricity_output_in_gwh";
    if (isElec(a) && !isElec(b)) return 1;
    if (!isElec(a) && isElec(b)) return -1;
    return 0;
  });

  const sortFuels = (
    fuels: { fuel: string; value: number }[],
    sector: string
  ) => {
    const filtered =
      sector === "18_electricity_output_in_gwh"
        ? fuels.filter(
            (item) =>
              !fuelMeta.find((f) => f.key === item.fuel)?.hide_in_elec_gen
          )
        : fuels;
    const nonZero = filtered.filter((f) => Number(f.value) !== 0);
    return nonZero.sort(
      (a, b) => (FUEL_ORDER[a.fuel] ?? 99) - (FUEL_ORDER[b.fuel] ?? 99)
    );
  };

  const elecLabel = useMemo(() => {
    return "Electricity generation (2023)";
  }, []);

  const chartSpan = 70; // percentage span for bars, leaves headroom

  const computeScale = (
    sectorKey: string,
    fuels: { fuel: string; value: number }[]
  ) => {
    if (!fuels.length) {
      return { range: 1, baselineScaled: 0, maxLabel: 0, minLabel: 0 };
    }
    const values = fuels.map((f) => Number(f.value) || 0);
    const localMax = Math.max(...values);
    const localMin = Math.min(...values);

    if (sectorKey === "net_imports") {
      const minVal = Math.min(0, localMin);
      const maxVal = Math.max(0, localMax);
      const range = Math.abs(minVal) + Math.max(maxVal, 0);
      const baselinePercent = range ? (Math.abs(minVal) / range) * 100 : 0;
      return {
        range: range || 1,
        baselineScaled: (baselinePercent / 100) * chartSpan,
        maxLabel: maxVal,
        minLabel: minVal,
      };
    }
    const cappedMin = Math.min(0, localMin);
    const cappedMax = Math.max(0, localMax);
    const hasPositive = cappedMax > 0;
    const hasNegative = cappedMin < 0;
    const range =
      hasPositive && hasNegative
        ? cappedMax - cappedMin
        : Math.max(cappedMax, Math.abs(cappedMin)) || 1;
    const baselinePercent =
      hasPositive && hasNegative
        ? (-cappedMin / (cappedMax - cappedMin)) * 100
        : hasPositive
        ? 0
        : 100;
    return {
      range,
      baselineScaled: (baselinePercent / 100) * chartSpan,
      maxLabel: cappedMax,
      minLabel: cappedMin,
    };
  };

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
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}
      >
        {chartSectors.map((sectorKey) => {
          const fuels = sortFuels(profile.sectors[sectorKey] ?? [], sectorKey);
          const barCount = Math.max(1, fuels.length);
          const sizing = computeCardSizing(barCount, sectorKey);
          const sectorTitle =
            sectorKey === "18_electricity_output_in_gwh"
              ? elecLabel
              : SECTOR_LABELS[sectorKey] ?? sectorKey;
          const { range, baselineScaled, maxLabel, minLabel } = computeScale(
            sectorKey,
            fuels
          );
          const barGap =
            fuels.length >= 10 ? "4px" : fuels.length >= 7 ? "6px" : "10px";
          const gridColumnWidth = "minmax(28px, 1fr)";
          return (
            <div
              key={sectorKey}
              className="border rounded p-3 bg-white dark:bg-slate-800 text-[13px]"
              style={{
                gridColumn: `span ${sizing.span} / span ${sizing.span}`,
                minWidth: `${sizing.minWidth}px`,
              }}
            >
              <div className="flex items-baseline mb-2">
                <p className="text-sm font-semibold">{sectorTitle}</p>
              </div>
              {fuels.length === 0 ? (
                <p className="text-xs text-gray-500">No data</p>
              ) : (
                <div
                  className="relative h-48 w-full grid items-start"
                  style={{
                    paddingLeft: "36px",
                    paddingTop: "0px",
                    gap: barGap,
                    gridTemplateColumns: `repeat(auto-fit, ${gridColumnWidth})`,
                  }}
                >
                  <div className="absolute left-[30px] top-0 bottom-0 w-px bg-gray-300 dark:bg-slate-600" />
                  <div
                    className="absolute top-0 text-[10px] text-gray-500 dark:text-gray-400 w-12 text-center leading-tight"
                    style={{ left: "-18px" }}
                  >
                    {formatEnergy(maxLabel)}
                  </div>
                  <div
                    className="absolute bottom-0 text-[10px] text-gray-500 dark:text-gray-400 w-12 text-center leading-tight"
                    style={{ left: "-18px" }}
                  >
                    {formatEnergy(minLabel)}
                  </div>
                  <div
                    className="absolute h-px bg-gray-400 dark:bg-slate-500 w-full"
                    style={{ bottom: `${baselineScaled}%`, left: 0 }}
                  />
                  {fuels.map((item) => {
                    const numericValue = Number(item.value) || 0;
                    const heightPercent =
                      (Math.abs(numericValue) / range) * chartSpan;
                    const isPositive = numericValue >= 0;
                    const color = fuelColors[item.fuel] ?? fuelColors.other;
                    const negativeBottom = Math.max(
                      0,
                      baselineScaled - heightPercent
                    );
                    return (
                      <div
                        key={item.fuel}
                        className="h-full relative flex flex-col items-center"
                        style={{ width: "100%" }}
                      >
                        <div
                          className="absolute left-1/4 right-1/4 rounded"
                          style={
                            isPositive
                              ? {
                                  height: `${heightPercent}%`,
                                  bottom: `${baselineScaled}%`,
                                  backgroundColor: color,
                                }
                              : {
                                  height: `${heightPercent}%`,
                                  bottom: `${negativeBottom}%`,
                                  backgroundColor: color,
                                }
                          }
                          title={`${formatFuelLabel(item.fuel)}: ${formatEnergy(
                            numericValue
                          )}`}
                        />
                        <p
                          className="text-[10px] mt-0 text-center text-gray-700 dark:text-gray-200 break-words leading-tight"
                          style={{
                            minHeight: "40px",
                            padding: "0 4px",
                            overflowWrap: "anywhere",
                          }}
                        >
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
