import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ToastContainer, Flip } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { EnergyGame } from "./components/EnergyGame";
import { useSettings } from "./hooks/useSettings";

function App() {
  const { t } = useTranslation();
  const [settingsData, updateSettings] = useSettings();

  useEffect(() => {
    if (settingsData.theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [settingsData.theme]);

  const toggleTheme = () =>
    updateSettings({
      theme: settingsData.theme === "dark" ? "light" : "dark",
    });

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
              <p className="text-xs uppercase tracking-wide text-gray-500">
                Energy balances
              </p>
              <h1 className="text-4xl font-bold tracking-wide">
                Energy Guessr
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Guess the economy from its energy balance charts.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600 dark:text-gray-300">
                {t("settings.theme")}
              </span>
              <button
                className="border px-2 py-1 text-xs rounded hover:bg-gray-50 dark:hover:bg-slate-800"
                type="button"
                onClick={toggleTheme}
              >
                {settingsData.theme === "dark" ? "Dark" : "Light"}
              </button>
            </div>
          </header>
          <div className="mt-4">
            <EnergyGame settingsData={settingsData} />
          </div>
        </div>
      </div>
    </>
  );
}

export default App;
