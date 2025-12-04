import React, { useMemo } from "react";
import CopyToClipboard from "react-copy-to-clipboard";
import { DateTime, Interval } from "luxon";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";
import { generateSquareCharacters } from "../domain/geography";
import { EnergyGuess } from "../domain/energy";

const START_DATE = DateTime.fromISO("2025-02-12");

interface EnergyShareProps {
  guesses: EnergyGuess[];
  dayString: string;
  theme: "light" | "dark";
}

export function EnergyShare({ guesses, dayString, theme }: EnergyShareProps) {
  const { t } = useTranslation();

  const shareText = useMemo(() => {
    const guessCount =
      guesses[guesses.length - 1]?.proximity === 100 ? guesses.length : "X";
    const dayCount = Math.floor(
      Interval.fromDateTimes(START_DATE, DateTime.fromISO(dayString)).length(
        "day"
      )
    );
    const title = `#EnergyGraphle #${dayCount} ${guessCount}/6`;

    const guessString = guesses
      .map((guess) => generateSquareCharacters(guess.proximity, theme).join(""))
      .join("\n");

    const origin =
      typeof window !== "undefined" ? window.location.origin : "energy-game";

    return [title, guessString, origin].join("\n");
  }, [dayString, guesses, theme]);

  return (
    <CopyToClipboard
      text={shareText}
      onCopy={() => toast(t("copy"))}
      options={{ format: "text/plain" }}
    >
      <button className="border-2 px-4 uppercase bg-green-600 hover:bg-green-500 active:bg-green-700 text-white w-full">
        {t("share")}
      </button>
    </CopyToClipboard>
  );
}
