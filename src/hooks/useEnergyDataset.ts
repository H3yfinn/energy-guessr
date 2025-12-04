import { useEffect, useState } from "react";
import {
  EnergyDataset,
  EnergyProfile,
  FuelValue,
  getMaxDistance,
  getSampleDataset,
} from "../domain/energy";

type DatasetSource = "user-file" | "sample";

interface EnergyDatasetState {
  dataset: EnergyDataset | null;
  years: number[];
  selectedYear: number | null;
  setYear: (year: number) => void;
  maxDistance: number;
  loading: boolean;
  error?: string;
  source: DatasetSource;
}

export function useEnergyDataset(): EnergyDatasetState {
  const noopSetYear = (year: number) => {
    // Helpful warning for single-year datasets or uninitialized state
    // eslint-disable-next-line no-console
    console.warn(
      `Year change ignored (no multi-year dataset loaded). Requested ${year}`
    );
  };

  const [state, setState] = useState<EnergyDatasetState>({
    dataset: null,
    years: [],
    selectedYear: null,
    setYear: noopSetYear,
    maxDistance: 1,
    loading: true,
    source: "sample",
  });

  useEffect(() => {
    let cancelled = false;

    function toNumber(value: unknown): number {
      if (typeof value === "number" && Number.isFinite(value)) {
        return value;
      }
      if (typeof value === "string") {
        const cleaned = value.replace(/,/g, "").trim();
        const parsed = Number(cleaned);
        return Number.isFinite(parsed) ? parsed : 0;
      }
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    function normalizeDataset(dataset: EnergyDataset): EnergyDataset {
      const normalizeProfile = (profile: EnergyProfile): EnergyProfile => {
        const normalizedSectors: Record<string, FuelValue[]> = {};
        Object.entries(profile.sectors).forEach(([sectorKey, fuels]) => {
          normalizedSectors[sectorKey] = fuels.map((fuel) => ({
            fuel: fuel.fuel,
            value: toNumber(fuel.value),
          }));
        });
        return { ...profile, sectors: normalizedSectors };
      };

      return {
        ...dataset,
        profiles: dataset.profiles.map(normalizeProfile),
      };
    }

    type MultiYear = {
      years: number[];
      defaultYear?: number;
      datasets: Record<string, EnergyDataset>;
      scenario?: string;
    };

    async function fetchDataset(
      path: string
    ): Promise<EnergyDataset | MultiYear> {
      const response = await fetch(path, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Failed to load data: ${response.statusText}`);
      }
      const raw = (await response.json()) as EnergyDataset | MultiYear;
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.debug("[energy] fetched", path, {
          hasDatasets: (raw as MultiYear).datasets !== undefined,
          years: (raw as MultiYear).years,
          year: (raw as EnergyDataset).year,
        });
      }
      if ((raw as MultiYear).datasets) {
        return raw;
      }
      return normalizeDataset(raw as EnergyDataset);
    }

    async function loadDataset() {
      try {
        const raw = await fetchDataset("data/energy-profiles.json");
        if (!cancelled) {
          applyDataset(raw, "user-file");
        }
      } catch (error: unknown) {
        try {
          const sampleRaw = await fetchDataset(
            "data/energy-profiles.sample.json"
          );
          if (!cancelled) {
            applyDataset(sampleRaw, "sample");
          }
        } catch {
          if (!cancelled) {
            const sample = getSampleDataset();
            setState({
              dataset: sample,
              years: [sample.year],
              selectedYear: sample.year,
              setYear: noopSetYear,
              maxDistance: getMaxDistance(sample),
              loading: false,
              source: "sample",
              error: undefined,
            });
          }
        }
      }
    }

    function applyDataset(
      raw: EnergyDataset | MultiYear,
      source: DatasetSource
    ) {
      // Multi-year payload
      if ((raw as MultiYear).datasets) {
        const multi = raw as MultiYear;
        const datasetEntries = Object.entries(multi.datasets || {});
        if (datasetEntries.length === 0) {
          throw new Error("No datasets found in multi-year payload");
        }
        const years = (
          multi.years || Object.keys(multi.datasets).map(Number)
        ).sort((a, b) => a - b);
        const defaultYear =
          multi.defaultYear && multi.datasets[String(multi.defaultYear)]
            ? multi.defaultYear
            : years[0];
        const pickYear = (year: number): EnergyDataset => {
          const chosen =
            multi.datasets[String(year)] ||
            multi.datasets[String(defaultYear)] ||
            datasetEntries[0][1];
          if (!chosen) {
            throw new Error("No dataset found for requested year");
          }
          return normalizeDataset(chosen);
        };

        const initialDataset = pickYear(defaultYear);
        const setYear = (year: number) => {
          if (cancelled) return;
          const chosenYear = years.includes(year) ? year : defaultYear;
          const nextDataset = pickYear(chosenYear);
          setState((prev) => ({
            ...prev,
            dataset: nextDataset,
            selectedYear: chosenYear,
            maxDistance: getMaxDistance(nextDataset),
            loading: false,
            source,
          }));
        };

        setState({
          dataset: initialDataset,
          years,
          selectedYear: defaultYear,
          setYear,
          maxDistance: getMaxDistance(initialDataset),
          loading: false,
          source,
        });
        return;
      }

      // Single-year payload
      const dataset = normalizeDataset(raw as EnergyDataset);
      setState({
        dataset,
        years: [dataset.year],
        selectedYear: dataset.year,
        setYear: noopSetYear,
        maxDistance: getMaxDistance(dataset),
        loading: false,
        source,
      });
    }

    loadDataset();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
