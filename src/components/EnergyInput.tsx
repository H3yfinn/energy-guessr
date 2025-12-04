import { t } from "i18next";
import React, { useState } from "react";
import Autosuggest from "react-autosuggest";
import { sanitizeEconomyName } from "../domain/energy";

interface EnergyInputProps {
  currentGuess: string;
  setCurrentGuess: (guess: string) => void;
  options: string[];
}

export function EnergyInput({
  currentGuess,
  setCurrentGuess,
  options,
}: EnergyInputProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);

  return (
    <Autosuggest
      suggestions={suggestions}
      onSuggestionsFetchRequested={({ value }) =>
        setSuggestions(
          options.filter((name) =>
            sanitizeEconomyName(name).includes(sanitizeEconomyName(value))
          )
        )
      }
      onSuggestionsClearRequested={() => setSuggestions([])}
      getSuggestionValue={(suggestion) => suggestion}
      renderSuggestion={(suggestion) => (
        <div className="border-2 dark:bg-slate-800 dark:text-slate-100">
          {suggestion}
        </div>
      )}
      containerProps={{
        className: "border-2 flex-auto relative",
      }}
      inputProps={{
        className: "w-full dark:bg-slate-800 dark:text-slate-100",
        placeholder: t("placeholder"),
        value: currentGuess,
        onChange: (_e, { newValue }) => setCurrentGuess(newValue),
      }}
      renderSuggestionsContainer={({ containerProps, children }) => (
        <div
          {...containerProps}
          className={`${containerProps.className} absolute bottom-full w-full bg-white mb-1 divide-x-2 max-h-52 overflow-auto`}
        >
          {children}
        </div>
      )}
    />
  );
}
