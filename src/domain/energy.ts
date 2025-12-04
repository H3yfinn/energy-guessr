import seedrandom from "seedrandom";

export interface FuelValue {
  fuel: string;
  value: number;
}

export type SectorKey =
  | "07_total_primary_energy_supply"
  | "12_total_final_consumption"
  | "09_total_transformation_sector"
  | string;

export interface EnergyProfile {
  economy: string;
  name: string;
  chartImage?: string;
  sectors: Record<SectorKey, FuelValue[]>;
}

export interface EnergyDataset {
  year: number;
  scenario: string;
  sectors: SectorKey[];
  profiles: EnergyProfile[];
}

export interface EnergyDistance {
  distance: number;
  maxDistance: number;
  proximity: number;
}

export interface EnergyGuess {
  name: string;
  distance: number;
  proximity: number;
  total: number;
  totalProximity: number;
  tpes: number;
  tfc: number;
  elecGen: number;
  netImports: number;
}

const SAMPLE_DATASET: EnergyDataset = {
  year: 2020,
  scenario: "reference",
  sectors: [
    "07_total_primary_energy_supply",
    "12_total_final_consumption",
    "09_total_transformation_sector",
  ],
  profiles: [
    {
      economy: "01_AUS",
      name: "Australia",
      chartImage: "01_AUS.png",
      sectors: {
        "07_total_primary_energy_supply": [
          { fuel: "coal", value: 3200 },
          { fuel: "gas", value: 1900 },
          { fuel: "oil", value: 1600 },
          { fuel: "renewables", value: 850 },
        ],
        "12_total_final_consumption": [
          { fuel: "industry", value: 1800 },
          { fuel: "transport", value: 1400 },
          { fuel: "buildings", value: 700 },
          { fuel: "other", value: 450 },
        ],
        "09_total_transformation_sector": [
          { fuel: "power", value: 2100 },
          { fuel: "heat", value: 200 },
          { fuel: "bunkers", value: 120 },
        ],
      },
    },
    {
      economy: "02_CAN",
      name: "Canada",
      chartImage: "02_CAN.png",
      sectors: {
        "07_total_primary_energy_supply": [
          { fuel: "coal", value: 800 },
          { fuel: "gas", value: 2500 },
          { fuel: "oil", value: 2200 },
          { fuel: "renewables", value: 1600 },
        ],
        "12_total_final_consumption": [
          { fuel: "industry", value: 1700 },
          { fuel: "transport", value: 1300 },
          { fuel: "buildings", value: 900 },
          { fuel: "other", value: 400 },
        ],
        "09_total_transformation_sector": [
          { fuel: "power", value: 1700 },
          { fuel: "heat", value: 180 },
          { fuel: "bunkers", value: 90 },
        ],
      },
    },
    {
      economy: "03_JPN",
      name: "Japan",
      chartImage: "03_JPN.png",
      sectors: {
        "07_total_primary_energy_supply": [
          { fuel: "coal", value: 1800 },
          { fuel: "gas", value: 2100 },
          { fuel: "oil", value: 2600 },
          { fuel: "renewables", value: 700 },
        ],
        "12_total_final_consumption": [
          { fuel: "industry", value: 1900 },
          { fuel: "transport", value: 1100 },
          { fuel: "buildings", value: 950 },
          { fuel: "other", value: 380 },
        ],
        "09_total_transformation_sector": [
          { fuel: "power", value: 2200 },
          { fuel: "heat", value: 160 },
          { fuel: "bunkers", value: 150 },
        ],
      },
    },
  ],
};

export function sanitizeEconomyName(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[- '()]/g, "")
    .toLowerCase();
}

function valueForFuel(
  sector: Record<SectorKey, FuelValue[]>,
  sectorKey: SectorKey,
  fuel: string
): number {
  return (
    sector[sectorKey]?.find(
      (item) => sanitizeEconomyName(item.fuel) === sanitizeEconomyName(fuel)
    )?.value ?? 0
  );
}

export function profileDistance(
  target: EnergyProfile,
  guess: EnergyProfile
): number {
  const sectorKeys = Array.from(
    new Set<SectorKey>([
      ...Object.keys(target.sectors),
      ...Object.keys(guess.sectors),
    ] as SectorKey[])
  );

  let total = 0;

  sectorKeys.forEach((sectorKey) => {
    const fuels = Array.from(
      new Set<string>([
        ...(target.sectors[sectorKey] ?? []).map((fuel) => fuel.fuel),
        ...(guess.sectors[sectorKey] ?? []).map((fuel) => fuel.fuel),
      ])
    );

    fuels.forEach((fuel) => {
      const delta = Math.abs(
        valueForFuel(target.sectors, sectorKey, fuel) -
          valueForFuel(guess.sectors, sectorKey, fuel)
      );
      total += delta;
    });
  });

  return total;
}

export function getMaxDistance(dataset: EnergyDataset): number {
  let max = 0;

  dataset.profiles.forEach((a, index) => {
    for (let i = index + 1; i < dataset.profiles.length; i += 1) {
      const b = dataset.profiles[i];
      max = Math.max(max, profileDistance(a, b));
    }
  });

  return max || 1;
}

export function proximityFromDistance(
  distance: number,
  maxDistance: number
): number {
  const clamped = Math.max(Math.min(distance, maxDistance), 0);
  return Math.round(((maxDistance - clamped) / maxDistance) * 100);
}

export function formatEnergy(value: number): string {
  const absValue = Math.abs(value);
  if (absValue >= 1000) {
    const ejValue = value / 1000;
    const formatted = ejValue.toLocaleString("en-US", {
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    });
    return `${formatted} EJ`;
  }
  const rounded = Math.round(value);
  const formatted = rounded.toLocaleString("en-US");
  return `${formatted} PJ`;
}

export function totalEnergy(profile: EnergyProfile): number {
  return Object.values(profile.sectors).reduce(
    (sum, fuels) =>
      sum + fuels.reduce((acc, fuel) => acc + (Number(fuel.value) || 0), 0),
    0
  );
}

export function sectorTotal(profile: EnergyProfile, key: string): number {
  return (profile.sectors[key] ?? []).reduce(
    (sum, item) => sum + (Number(item.value) || 0),
    0
  );
}

export function netImports(profile: EnergyProfile): number {
  const imports = sectorTotal(profile, "02_imports");
  const exports = sectorTotal(profile, "03_exports");
  return imports - Math.abs(exports);
}

export function netImportsByFuel(profile: EnergyProfile): FuelValue[] {
  const imports = profile.sectors["02_imports"] ?? [];
  const exports = profile.sectors["03_exports"] ?? [];

  const fuelMap = new Map<string, number>();

  imports.forEach((item) => {
    fuelMap.set(
      item.fuel,
      (fuelMap.get(item.fuel) || 0) + (Number(item.value) || 0)
    );
  });

  exports.forEach((item) => {
    fuelMap.set(
      item.fuel,
      (fuelMap.get(item.fuel) || 0) - Math.abs(Number(item.value) || 0)
    );
  });

  return Array.from(fuelMap.entries()).map(([fuel, value]) => ({
    fuel,
    value,
  }));
}

export function chooseProfile(
  dataset: EnergyDataset,
  dayString: string
): EnergyProfile {
  const rng = seedrandom.alea(dayString);
  const index = Math.floor(rng() * dataset.profiles.length);
  return dataset.profiles[index];
}

export function findProfile(
  dataset: EnergyDataset,
  guessName: string
): EnergyProfile | undefined {
  const sanitizedGuess = sanitizeEconomyName(guessName);
  return dataset.profiles.find(
    (profile) => sanitizeEconomyName(profile.name) === sanitizedGuess
  );
}

export function getSampleDataset(): EnergyDataset {
  return SAMPLE_DATASET;
}
