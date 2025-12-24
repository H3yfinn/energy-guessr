import { useEffect, useState } from "react";
import {
  EnergyDataset,
  EnergyProfile,
  FuelValue,
  getMaxDistance,
  getSampleDataset,
} from "../domain/energy";

type DatasetSource = "user-file" | "sample" | "world";

interface EnergyDatasetState {
  dataset: EnergyDataset | null;
  years: number[];
  selectedYear: number | null;
  setYear: (year: number, preferredEconomy?: string) => void;
  maxDistance: number;
  loading: boolean;
  error?: string;
  source: DatasetSource;
  available: {
    apec: boolean;
    world: boolean;
  };
}

export function useEnergyDataset(
  preferred: "apec" | "world" | "auto" = "auto"
): EnergyDatasetState {
  const primaryPath = "data/energy-profiles-apec.json";
  const primaryIndexPath = "data/energy-profiles-apec.index.json";
  const worldPath = "data/energy-profiles-un-ei.json";
  const worldIndexPath = "data/energy-profiles-un-ei.index.json";
  const samplePath = "data/energy-profiles.sample.json";

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
    available: { apec: false, world: false },
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

    type IndexPayload = {
      years: number[];
      defaultYear?: number;
      scenario?: string;
      files?: Record<string, string>;
      groups?: Array<{ id: string; file: string; economies: string[] }>;
      year_groups?: Record<
        string,
        Array<{ id: string; file: string; economies: string[] }>
      >;
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

    async function fetchIndex(path: string): Promise<IndexPayload> {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to load index: ${res.statusText}`);
      }
      const idx = (await res.json()) as IndexPayload;
      if (
        !idx.years ||
        idx.years.length === 0 ||
        (!idx.files && !idx.groups && !idx.year_groups)
      ) {
        throw new Error("Invalid index payload");
      }
      return idx;
    }

    async function loadDataset() {
      const availability = { apec: false, world: false };

      // Build attempt order based on preference
      const attempts: Array<{
        path: string;
        source: DatasetSource;
        mode: "index" | "full";
      }> = [];
      if (preferred === "world") {
        attempts.push({
          path: worldIndexPath,
          source: "world",
          mode: "index",
        });
        attempts.push({ path: worldPath, source: "world", mode: "full" });
        attempts.push({
          path: primaryIndexPath,
          source: "user-file",
          mode: "index",
        });
        attempts.push({ path: primaryPath, source: "user-file", mode: "full" });
      } else {
        attempts.push({
          path: primaryIndexPath,
          source: "user-file",
          mode: "index",
        });
        attempts.push({ path: primaryPath, source: "user-file", mode: "full" });
        attempts.push({
          path: worldIndexPath,
          source: "world",
          mode: "index",
        });
        attempts.push({ path: worldPath, source: "world", mode: "full" });
      }
      attempts.push({ path: samplePath, source: "sample", mode: "full" });

      let loaded = false;
      for (const attempt of attempts) {
        try {
          if (attempt.mode === "index") {
            const idx = await fetchIndex(attempt.path);
            if (attempt.source === "world") availability.world = true;
            if (!cancelled) {
              await applyIndexDataset(
                idx,
                attempt.path,
                attempt.source,
                availability
              );
            }
            loaded = true;
            break;
          }
          const raw = await fetchDataset(attempt.path);
          if (attempt.source === "user-file") availability.apec = true;
          if (attempt.source === "world") availability.world = true;
          if (!cancelled) {
            applyDataset(raw, attempt.source, availability);
          }
          loaded = true;
          break;
        } catch (error: unknown) {
          if (process.env.NODE_ENV !== "production") {
            // eslint-disable-next-line no-console
            console.warn("[energy] failed to load", attempt.path, error);
          }
        }
      }

      // Probe availability for both datasets regardless of which loaded first
      const probePaths: Array<{ path: string; source: DatasetSource }> = [
        { path: primaryPath, source: "user-file" },
        { path: primaryIndexPath, source: "user-file" },
        { path: worldPath, source: "world" },
        { path: worldIndexPath, source: "world" },
      ];
      await Promise.all(
        probePaths.map(async (p) => {
          try {
            const res = await fetch(p.path, {
              method: "HEAD",
              cache: "no-store",
            });
            if (res.ok) {
              if (p.source === "user-file") availability.apec = true;
              if (p.source === "world") availability.world = true;
            }
          } catch {
            // ignore
          }
        })
      );

      // If we already loaded a dataset, update availability flags without changing data
      if (loaded && !cancelled) {
        setState((prev) => ({
          ...prev,
          available: availability,
        }));
        return;
      }

      // Fallback to built-in sample
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
          available: availability,
          error: undefined,
        });
      }
    }

    function applyDataset(
      raw: EnergyDataset | MultiYear,
      source: DatasetSource,
      availability: { apec: boolean; world: boolean }
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
        const normalizedCache: Record<number, EnergyDataset> = {};
        const pickYear = (year: number): EnergyDataset => {
          const chosen =
            multi.datasets[String(year)] ||
            multi.datasets[String(defaultYear)] ||
            datasetEntries[0][1];
          if (!chosen) {
            throw new Error("No dataset found for requested year");
          }
          const yr = Number((chosen as EnergyDataset).year || year);
          if (!normalizedCache[yr]) {
            normalizedCache[yr] = normalizeDataset(chosen);
          }
          return normalizedCache[yr];
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
          available: availability,
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
        available: availability,
      });
    }

    async function applyIndexDataset(
      index: IndexPayload,
      indexPath: string,
      source: DatasetSource,
      availability: { apec: boolean; world: boolean }
    ) {
      const years = (index.years || []).slice().sort((a, b) => a - b);
      if (years.length === 0) {
        throw new Error("Index contained no years");
      }
      const indexDir =
        indexPath.lastIndexOf("/") >= 0
          ? indexPath.slice(0, indexPath.lastIndexOf("/") + 1)
          : "";
      const defaultYear =
        index.defaultYear && years.includes(index.defaultYear)
          ? index.defaultYear
          : years[0];

      // Year-first group index
      if (index.year_groups && Object.keys(index.year_groups).length > 0) {
        const cache: Record<string, EnergyDataset> = {};
        const loadGroupYear = async (
          year: number,
          groupId?: string
        ): Promise<EnergyDataset> => {
          const yearStr = String(year);
          const groups = index.year_groups?.[yearStr] || [];
          const pickGroup =
            groupId && groups.find((g) => g.id === groupId)
              ? groupId
              : groups[0]?.id;
          const cacheKey = `${yearStr}:${pickGroup || "all"}`;
          if (cache[cacheKey]) return cache[cacheKey];
          const group = groups.find((g) => g.id === pickGroup) || groups[0];
          if (!group) {
            throw new Error(`No group shard found for year ${yearStr}`);
          }
          const path = `${indexDir}${group.file}`;
          const data = (await fetchDataset(path)) as EnergyDataset;
          cache[cacheKey] = normalizeDataset(data);
          return cache[cacheKey];
        };

        const initialDataset = await loadGroupYear(defaultYear);
        const setYear = async (year: number, preferredEconomy?: string) => {
          if (cancelled) return;
          const chosen = years.includes(year) ? year : defaultYear;
          try {
            let groupId: string | undefined;
            if (preferredEconomy) {
              const groups = index.year_groups?.[String(chosen)] || [];
              const match = groups.find((g) =>
                g.economies?.includes(preferredEconomy)
              );
              groupId = match?.id;
            }
            const nextDataset = await loadGroupYear(chosen, groupId);
            if (cancelled) return;
            setState((prev) => ({
              ...prev,
              dataset: nextDataset,
              selectedYear: chosen,
              maxDistance: getMaxDistance(nextDataset),
              loading: false,
              source,
            }));
          } catch (e) {
            if (process.env.NODE_ENV !== "production") {
              // eslint-disable-next-line no-console
              console.warn("[energy] failed to load year", chosen, e);
            }
          }
        };

        setState({
          dataset: initialDataset,
          years,
          selectedYear: defaultYear,
          setYear,
          maxDistance: getMaxDistance(initialDataset),
          loading: false,
          source,
          available: availability,
        });
        return;
      }

      // Legacy per-year index support
      const cache: Record<number, EnergyDataset> = {};
      const loadYear = async (year: number): Promise<EnergyDataset> => {
        if (cache[year]) return cache[year];
        const fileName = index.files?.[String(year)];
        if (!fileName) {
          throw new Error(`No file mapping for year ${year}`);
        }
        const path = `${indexDir}${fileName}`;
        const dataset = (await fetchDataset(path)) as EnergyDataset;
        cache[year] = normalizeDataset(dataset);
        return cache[year];
      };

      const initialDataset = await loadYear(defaultYear);
      const setYear = async (year: number) => {
        if (cancelled) return;
        const chosen = years.includes(year) ? year : defaultYear;
        try {
          const nextDataset = await loadYear(chosen);
          if (cancelled) return;
          setState((prev) => ({
            ...prev,
            dataset: nextDataset,
            selectedYear: chosen,
            maxDistance: getMaxDistance(nextDataset),
            loading: false,
            source,
          }));
        } catch (e) {
          if (process.env.NODE_ENV !== "production") {
            // eslint-disable-next-line no-console
            console.warn("[energy] failed to load year", chosen, e);
          }
        }
      };

      setState({
        dataset: initialDataset,
        years,
        selectedYear: defaultYear,
        setYear,
        maxDistance: getMaxDistance(initialDataset),
        loading: false,
        source,
        available: availability,
      });
    }

    loadDataset();
    return () => {
      cancelled = true;
    };
  }, [preferred]);

  return state;
}
