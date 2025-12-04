import React from "react";
import { EnergyGuess } from "../domain/energy";
import { EnergyGuessRow } from "./EnergyGuessRow";

interface EnergyGuessesProps {
  rowCount: number;
  guesses: EnergyGuess[];
}

export function EnergyGuesses({ rowCount, guesses }: EnergyGuessesProps) {
  return (
    <div>
      <div className="grid grid-cols-5 gap-1 text-center text-xs font-semibold mb-1">
        <div className="border-2 h-8 flex items-center justify-center">
          Economy
        </div>
        <div className="border-2 h-8 flex items-center justify-center">TFC</div>
        <div className="border-2 h-8 flex items-center justify-center">
          TPES
        </div>
        <div className="border-2 h-8 flex items-center justify-center">
          Elec gen
        </div>
        <div className="border-2 h-8 flex items-center justify-center">
          Net imports
        </div>
      </div>
      <div className="grid grid-cols-5 gap-1 text-center">
        {Array.from(Array(rowCount).keys()).map((index) => (
          <EnergyGuessRow key={index} guess={guesses[index]} />
        ))}
      </div>
    </div>
  );
}
