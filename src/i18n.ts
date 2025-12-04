import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

const resources = {
  en: {
    translation: {
      placeholder: "Economy or market...",
      guess: "Guess",
      share: "Share",
      showOnGoogleMaps: "Open on Google Maps",
      welldone: "Well done!",
      unknownCountry: "Unknown economy!",
      copy: "Copied results to clipboard",
      showCountry: "Show chart",
      cancelRotation: "Cancel rotation",
      settings: {
        title: "Settings",
        distanceUnit: "Unit of distance",
        theme: "Theme",
        difficultyModifiers: "Difficulty modifiers",
        startingNextDay: "Starting the next day!",
        noImageMode: "Hide image for more of a challenge.",
        rotationMode: "Rotate randomly.",
      },
      buyMeACoffee: "Buy me a coffee!",
    },
  },
  fr: {
    translation: {
      placeholder: "Economie ou marché...",
      guess: "Deviner",
      share: "Partager",
      showOnGoogleMaps: "Ouvrir sur Google Maps",
      welldone: "Bien joué !",
      unknownCountry: "Economie inconnue !",
      copy: "Résultat copié !",
      showCountry: "Afficher le graphique",
      cancelRotation: "Annuler la rotation",
      settings: {
        title: "Paramètres",
        distanceUnit: "Unité de distance",
        theme: "Thème",
        difficultyModifiers: "Modificateurs de difficulté",
        startingNextDay: "A partir du lendemain !",
        noImageMode: "Cache l'image pour plus de challenge.",
        rotationMode: "Tourne l'image de manière aléatoire.",
      },
      buyMeACoffee: "Offrez moi un café !",
    },
  },
};

i18n
  .use(initReactI18next)
  .use(LanguageDetector)
  .init({
    resources,
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
