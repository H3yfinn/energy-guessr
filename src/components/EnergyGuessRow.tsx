import React from "react";
import { EnergyGuess, formatEnergy } from "../domain/energy";

interface EnergyGuessRowProps {
  guess?: EnergyGuess;
  compact?: boolean;
}

export function EnergyGuessRow({
  guess,
  compact = false,
}: EnergyGuessRowProps) {
  if (guess == null) {
    return (
      <div
        className={`col-span-5 border-2 ${
          compact ? "py-2 text-sm leading-tight" : "h-8"
        } bg-gray-200 dark:bg-slate-600`}
      />
    );
  }

  const isCorrect = guess.totalProximity === 100;
  const flashClass = isCorrect ? "guess-flash-correct" : "guess-flash-wrong";
  const rowClass = isCorrect
    ? `border-2 ${flashClass} ${
        compact ? "py-1 text-sm leading-tight" : "h-8 text-xs"
      } flex items-center justify-center bg-green-50 dark:bg-green-900/30`
    : `border-2 ${flashClass} ${
        compact ? "py-1 text-sm leading-tight" : "h-8 text-xs"
      } flex items-center justify-center bg-red-50 dark:bg-red-900/30`;

  return (
    <>
      <div className={rowClass + " col-span-1"}>
        <p className="text-ellipsis overflow-hidden whitespace-nowrap">
          {guess.name}
        </p>
      </div>
      <div className={rowClass + " col-span-1"}>{formatEnergy(guess.tfc)}</div>
      <div className={rowClass + " col-span-1"}>
        {formatEnergy(guess.production)}
      </div>
      <div className={rowClass + " col-span-1"}>
        {formatEnergy(guess.netImports)}
      </div>
      <div className={rowClass + " col-span-1"}>
        {formatEnergy(guess.elecGen)}
      </div>
    </>
  );
}
