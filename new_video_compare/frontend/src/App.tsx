import React, { useState } from "react";
import Dashboard from "./components/Dashboard";
import VideoComparison from "./components/VideoComparison";
import AutoPairForm from "./components/AutoPairForm";
import KnowledgeBase from "./components/KnowledgeBase";
import AutomationLogs from "./components/AutomationLogs";
import {
  BellIcon,
  ChartBarIcon,
  ListBulletIcon,
  BookOpenIcon,
  SunIcon,
  MoonIcon,
} from "@heroicons/react/24/outline";


import { useRouting } from "./hooks/useRouting";
import { useConnection } from "./hooks/useConnection";
import { useNotifications } from "./hooks/useNotifications";
import { useSettings } from "./hooks/useSettings";

function App() {
  const { selectedJob, handleSelectJob } = useRouting();
  const { backendStatus, wsStatus } = useConnection();
  const { 
    unreadNotifications, 
    recentErrors, 
    showNotifications, 
    setShowNotifications, 
    handleToggleNotifications 
  } = useNotifications();
  const [showAutoPair, setShowAutoPair] = useState(false);
  const [dashboardView, setDashboardView] = useState<"list" | "stats" | "kb" | "logs">("list");
  
  const { theme, setTheme, lang, setLang, t } = useSettings();





  const getStatusDot = (status: string) => {
    switch (status) {
      case "connected":
        return "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]";
      case "disconnected":
        return "bg-rose-400";
      case "checking":
      default:
        return "bg-amber-400 animate-pulse";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0d0e15] text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Navigation Header - VITO / VidiCom Style */}
      <nav className="bg-white dark:bg-[#12131c] shadow-md border-b border-slate-200 dark:border-white/10 print:hidden sticky top-0 z-40 backdrop-blur-md bg-opacity-95 dark:bg-opacity-95">
        <div className="max-w-7xl mx-auto px-6 py-3.5">
          <div className="flex items-center justify-between">
            {/* Logo VITO / VidiCom Style */}
            <div className="flex items-center space-x-4">
              <div
                className="flex items-center space-x-3.5 cursor-pointer group"
                onClick={() => { handleSelectJob(null); setDashboardView("list"); }}
              >
                <div className="w-11 h-11 bg-gradient-to-tr from-[#6816B0] via-[#350F9C] to-[#00FFFF] rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(73,96,230,0.45)] border border-white/20 transform group-hover:scale-105 transition-transform duration-200">
                  <svg
                    className="w-6 h-6 text-white drop-shadow-md"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.2}
                      d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-white uppercase font-sans">
                      New Video Compare
                    </h1>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-gradient-to-r from-[#6816B0] to-[#350F9C] text-white shadow-sm border border-purple-400/30">
                      v3.0
                    </span>
                  </div>
                  <p className="text-[11px] font-bold tracking-wider text-slate-500 dark:text-slate-400 uppercase">
                    {t.appSubtitle}
                  </p>
                </div>
              </div>
              {/* DEV environment badge */}
              {window.location.port === "3001" && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30 animate-pulse" title={t.devTooltip}>
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block"></span>
                  {t.devBadge}
                </span>
              )}
            </div>

            {/* Right Controls Bar */}
            <div className="flex items-center space-x-4">
              {/* Status Indicators */}
              <div className="flex items-center space-x-4 text-xs font-bold desktop:flex hidden text-slate-600 dark:text-slate-300">
                <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-white/10">
                  <div className={`w-2 h-2 rounded-full ${getStatusDot(backendStatus)}`}></div>
                  <span>{t.backendStatus}</span>
                </div>
                <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-white/10">
                  <div className={`w-2 h-2 rounded-full ${getStatusDot(wsStatus)}`}></div>
                  <span>{t.wsStatus}</span>
                </div>
              </div>

              <div className="h-6 w-px bg-slate-200 dark:bg-white/10 mx-1"></div>

              {/* Navigation Tabs */}
              <div className="flex bg-slate-100 dark:bg-slate-800/90 p-1 rounded-xl border border-slate-200 dark:border-white/10">
                <button
                  onClick={() => { handleSelectJob(null); setDashboardView("list"); }}
                  className={`inline-flex items-center px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    dashboardView === "list"
                      ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700/50'
                  }`}
                >
                  <ListBulletIcon className="w-4 h-4 mr-1.5" />
                  {t.navJobs}
                </button>
                <button
                  onClick={() => { handleSelectJob(null); setDashboardView("stats"); }}
                  className={`inline-flex items-center px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    dashboardView === "stats"
                      ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700/50'
                  }`}
                >
                  <ChartBarIcon className="w-4 h-4 mr-1.5" />
                  {t.navStats}
                </button>
                <button
                  onClick={() => { handleSelectJob(null); setDashboardView("kb"); }}
                  className={`inline-flex items-center px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    dashboardView === "kb"
                      ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700/50'
                  }`}
                >
                  <BookOpenIcon className="w-4 h-4 mr-1.5" />
                  {t.navKB}
                </button>
                <button
                  onClick={() => { handleSelectJob(null); setDashboardView("logs"); }}
                  className={`inline-flex items-center px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    dashboardView === "logs"
                      ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700/50'
                  }`}
                >
                  <ListBulletIcon className="w-4 h-4 mr-1.5" />
                  {t.navLogs}
                </button>
              </div>

              {/* Requirement 1 & 2: Theme Toggle & PL/EN Language Switcher */}
              <div className="flex items-center space-x-2 border-l border-slate-200 dark:border-white/10 pl-3">
                {/* Theme Toggle Button (Sun / Moon) */}
                <button
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-cyan-400 border border-slate-200 dark:border-white/10 transition-all"
                  title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
                >
                  {theme === "dark" ? (
                    <SunIcon className="w-4 h-4 text-amber-400" />
                  ) : (
                    <MoonIcon className="w-4 h-4 text-indigo-600" />
                  )}
                </button>

                {/* PL / EN Language Switcher Pill */}
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200 dark:border-white/10 text-xs font-black">
                  <button
                    onClick={() => setLang("PL")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      lang === "PL"
                        ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    PL
                  </button>
                  <button
                    onClick={() => setLang("EN")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      lang === "EN"
                        ? 'bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white shadow-md'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    EN
                  </button>
                </div>
              </div>

              {/* Notifications */}
              <div className="flex items-center space-x-1 relative notifications-container">
                <button 
                  onClick={handleToggleNotifications}
                  className={`p-2 focus:outline-none rounded-xl transition-colors border border-slate-200 dark:border-white/10 relative ${
                    showNotifications ? 'bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-white' : 'bg-slate-100 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                  title={t.systemNotifications}
                >
                  <BellIcon className="w-4 h-4" />
                  {unreadNotifications > 0 && (
                    <span className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white ring-2 ring-slate-900 animate-pulse">
                      {unreadNotifications}
                    </span>
                  )}
                </button>

                {showNotifications && (
                  <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl bg-white dark:bg-[#161824] shadow-2xl ring-1 ring-black ring-opacity-5 z-50 overflow-hidden divide-y divide-slate-100 dark:divide-white/10 border border-slate-200 dark:border-white/10">
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wider">
                        {t.systemErrors}
                      </span>
                      {recentErrors.length > 0 && (
                        <button 
                          onClick={() => { handleSelectJob(null); setDashboardView("logs"); setShowNotifications(false); }}
                          className="text-xs text-indigo-600 dark:text-cyan-400 hover:underline font-bold"
                        >
                          {t.viewLogs}
                        </button>
                      )}
                    </div>
                    <div className="max-h-80 overflow-y-auto divide-y divide-slate-100 dark:divide-white/5">
                      {recentErrors.length === 0 ? (
                        <div className="p-4 text-center text-xs text-slate-500 dark:text-slate-400">
                          {t.noSystemErrors}
                        </div>
                      ) : (
                        recentErrors.slice(0, 5).map((log) => (
                          <div 
                            key={log.id} 
                            className="p-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                          >
                            <div className="flex items-start justify-between space-x-2">
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 dark:bg-rose-900/30 text-rose-800 dark:text-rose-300">
                                {log.component === "desktop_app" ? "Desktop App" : log.component === "extension" ? "Rozszerzenie" : "Backend"}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                {new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p className="mt-1 text-xs font-bold text-slate-900 dark:text-white">
                              {log.cradle_id ? `Cradle ID: ${log.cradle_id}` : "Błąd Systemu"}
                            </p>
                            <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300" title={log.message}>
                              {log.message.length > 120 ? log.message.substring(0, 120) + "..." : log.message}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="flex-1">
        {selectedJob ? (
          <div>
            {/* Breadcrumb */}
            <div className="max-w-7xl mx-auto px-6 py-3">
              <nav className="flex" aria-label="Breadcrumb">
                <ol className="flex items-center space-x-3 text-xs font-bold">
                  <li>
                    <button
                      onClick={() => handleSelectJob(null)}
                      className="text-indigo-600 dark:text-cyan-400 hover:underline transition-colors"
                    >
                      {t.dashboardBreadcrumb}
                    </button>
                  </li>
                  <li>
                    <div className="flex items-center text-slate-400">
                      <svg
                        className="flex-shrink-0 h-4 w-4"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="ml-2 text-slate-600 dark:text-slate-300 font-semibold">
                        {selectedJob.job_name}
                      </span>
                    </div>
                  </li>
                </ol>
              </nav>
            </div>
            <VideoComparison 
              job={selectedJob} 
              onJobReanalyzed={() => handleSelectJob(null)}
              onBackToDashboard={() => handleSelectJob(null)}
              lang={lang}
              theme={theme}
            />
          </div>
        ) : dashboardView === "kb" ? (
          <KnowledgeBase onSelectJob={handleSelectJob} lang={lang} theme={theme} />
        ) : dashboardView === "logs" ? (
          <AutomationLogs lang={lang} theme={theme} />
        ) : (
          <Dashboard onSelectJob={handleSelectJob} viewMode={dashboardView as "list" | "stats"} lang={lang} theme={theme} />
        )}
      </div>

      {/* Auto-Pair Modal */}
      {showAutoPair && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
          <div className="relative mx-auto p-6 border border-slate-200 dark:border-white/10 w-full max-w-md shadow-2xl rounded-2xl bg-white dark:bg-[#161824]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-black text-slate-900 dark:text-white">
                Create Auto-Pair Job
              </h3>
              <button
                onClick={() => setShowAutoPair(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white rounded-xl p-1 transition-colors"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <AutoPairForm onClose={() => setShowAutoPair(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
