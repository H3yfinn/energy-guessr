import React, { useEffect, useState } from "react";
import { ToastContainer, Flip } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { EnergyGame } from "./components/EnergyGame";
import { useSettings } from "./hooks/useSettings";

function App() {
  const [settingsData] = useSettings();
  const [pageTitle, setPageTitle] = useState("Energy Guessr");

  useEffect(() => {
    if (settingsData.theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [settingsData.theme]);

  return (
    <>
      <ToastContainer
        hideProgressBar
        position="top-center"
        transition={Flip}
        theme={settingsData.theme}
        autoClose={2000}
        bodyClassName="font-bold text-center"
      />
      <div className="flex justify-center flex-auto dark:bg-slate-900 dark:text-slate-50 min-h-screen">
        <div className="w-full max-w-7xl flex flex-col p-4">
          <header className="border-b-2 border-gray-200 flex items-start justify-between pb-3">
            <div>
              <h1 className="text-4xl font-bold tracking-wide">{pageTitle}</h1>
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Guess the country from its energy balance charts.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
                type="button"
                onClick={() => {
                  const event = new CustomEvent("energy-show-glossary");
                  window.dispatchEvent(event);
                }}
              >
                Glossary
              </button>
              <button
                className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
                type="button"
                onClick={() => {
                  const event = new CustomEvent("energy-show-help");
                  window.dispatchEvent(event);
                }}
              >
                Show help
              </button>
            </div>
          </header>
          <div className="mt-4">
            <EnergyGame
              settingsData={settingsData}
              onTitleChange={(title) => setPageTitle(title || "Energy Guessr")}
            />
          </div>
        </div>
      </div>
    </>
  );
}

export default App;
