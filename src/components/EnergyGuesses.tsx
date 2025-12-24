import React from "react";
import { EnergyGuess } from "../domain/energy";
import { EnergyGuessRow } from "./EnergyGuessRow";

interface EnergyGuessesProps {
  rowCount: number;
  guesses: EnergyGuess[];
  hideTable?: boolean;
  compact?: boolean;
}

export function EnergyGuesses({
  rowCount,
  guesses,
  hideTable = false,
  compact = false,
}: EnergyGuessesProps) {
  if (hideTable) {
    return null;
  }

  const cellBase =
    "border-2 flex items-center justify-center text-center " +
    (compact ? "py-1 text-sm leading-tight" : "h-8 text-xs");
  const rows = guesses.filter(Boolean);
  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1">
      <div className="grid grid-cols-5 gap-1 text-center font-semibold text-xs">
        <div className={cellBase}>Country</div>
        <div className={cellBase}>Total final consumption</div>
        <div className={cellBase}>Production</div>
        <div className={cellBase}>Net imports</div>
        <div className={cellBase}>Electricity generation</div>
      </div>
      <div className="grid grid-cols-5 gap-1 text-center">
        {rows.map((guess, index) => (
          <EnergyGuessRow key={index} guess={guess} compact={compact} />
        ))}
      </div>
    </div>
  );
}
