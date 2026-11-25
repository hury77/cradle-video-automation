import React, { useEffect, useState } from "react";
import { translations, Language } from "../utils/translations";

interface SystemEngineBadgeProps {
  lang?: Language;
}

const SystemEngineBadge: React.FC<SystemEngineBadgeProps> = ({ lang = "PL" }) => {
  const t = translations[lang];
  const [engine, setEngine] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), 3000) : null;

    fetch("/api/v1/system/info", controller ? { signal: controller.signal } : undefined)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active) {
          setEngine(data && typeof data.decision_engine === "string" ? data.decision_engine : null);
        }
      })
      .catch(() => {
        if (active) {
          setEngine(null);
        }
      })
      .finally(() => {
        if (timer) clearTimeout(timer);
      });

    return () => {
      active = false;
      if (timer) clearTimeout(timer);
      if (controller) controller.abort();
    };
  }, []);

  if (!engine) {
    return null;
  }

  return (
    <div
      data-testid="system-engine-badge"
      className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-white/10 text-xs font-bold text-slate-600 dark:text-slate-300"
    >
      <span>⚙️</span>
      <span>
        {t.decisionEngineLabel}: <span className="font-mono">{engine}</span>
      </span>
    </div>
  );
};

export default SystemEngineBadge;
