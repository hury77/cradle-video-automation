import { useState, useEffect } from "react";
import { translations, Language } from "../utils/translations";

export function useSettings() {
  // Theme state ('dark' | 'light') - default 'dark' as in VITO/VidiCom brandbook
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("cradle_theme") as "dark" | "light") || "dark";
  });

  // Language state ('PL' | 'EN') - default 'PL'
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem("cradle_lang") as Language) || "PL";
  });

  const t = translations[lang];

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    localStorage.setItem("cradle_theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("cradle_lang", lang);
  }, [lang]);

  return { theme, setTheme, lang, setLang, t };
}
