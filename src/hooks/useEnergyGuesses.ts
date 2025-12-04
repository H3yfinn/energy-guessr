import { useCallback, useState } from "react";
import { EnergyGuess } from "../domain/energy";

const STORAGE_KEY = "energy-guesses";

function loadAllGuesses(): Record<string, EnergyGuess[]> {
  const storedGuesses = localStorage.getItem(STORAGE_KEY);
  return storedGuesses != null ? JSON.parse(storedGuesses) : {};
}

export function useEnergyGuesses(
  dayString: string
): [EnergyGuess[], (guess: EnergyGuess) => void, () => void] {
  const [guesses, setGuesses] = useState<EnergyGuess[]>(
    loadAllGuesses()[dayString] ?? []
  );

  const saveGuesses = useCallback(
    (newGuesses: EnergyGuess[]) => {
      const allGuesses = loadAllGuesses();
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          ...allGuesses,
          [dayString]: newGuesses,
        })
      );
    },
    [dayString]
  );

  const addGuess = useCallback(
    (newGuess: EnergyGuess) => {
      const newGuesses = [...guesses, newGuess];
      setGuesses(newGuesses);
      saveGuesses(newGuesses);
    },
    [guesses, saveGuesses]
  );

  const resetGuesses = useCallback(() => {
    const allGuesses = loadAllGuesses();
    delete allGuesses[dayString];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(allGuesses));
    setGuesses([]);
  }, [dayString]);

  return [guesses, addGuess, resetGuesses];
}
