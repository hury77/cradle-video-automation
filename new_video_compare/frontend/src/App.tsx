// frontend/src/App.tsx
import React, { useState, useEffect } from "react";
import Dashboard from "./components/Dashboard";
import VideoComparison from "./components/VideoComparison";
import AutoPairForm from "./components/AutoPairForm";
import KnowledgeBase from "./components/KnowledgeBase";
import AutomationLogs from "./components/AutomationLogs";
import { StandalonePlayer } from "./components/StandalonePlayer";
import { ComparisonJob } from "./types";
import {
  Cog6ToothIcon,
  BellIcon,
  UserIcon,
  PlusIcon,
  ChartBarIcon,
  ListBulletIcon,
  BookOpenIcon,
  PlayIcon
} from "@heroicons/react/24/outline";

import { compareApi } from "./services/api";

function App() {
  const [selectedJob, setSelectedJob] = useState<ComparisonJob | null>(null);
  const [showAutoPair, setShowAutoPair] = useState(false);
  const [dashboardView, setDashboardView] = useState<"list" | "stats" | "kb" | "logs" | "player">("list");
  const [backendStatus, setBackendStatus] = useState<
    "connected" | "disconnected" | "checking"
  >("checking");
  const [wsStatus, setWsStatus] = useState<
    "connected" | "disconnected" | "checking"
  >("checking");

  const [unreadNotifications, setUnreadNotifications] = useState<number>(0);
  const [recentErrors, setRecentErrors] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState<boolean>(false);

  // Handle initial URL and browser navigation
  useEffect(() => {
    const handleLocationChange = async () => {
      const path = window.location.pathname;
      const compareMatch = path.match(/^\/compare\/(\d+)$/);

      if (compareMatch) {
        const jobId = parseInt(compareMatch[1], 10);
        try {
          const job = await compareApi.getJob(jobId);
          setSelectedJob(job);
        } catch (error) {
          console.error("Failed to load job from URL", error);
          // Optional: redirect to dashboard or show error
          window.history.replaceState(null, "", "/");
          setSelectedJob(null);
        }
      } else {
        setSelectedJob(null);
      }
    };

    // Check initial URL
    handleLocationChange();

    // Listen for popstate (back/forward)
    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, []);

  const handleSelectJob = (job: ComparisonJob | null) => {
    setSelectedJob(job);
    if (job) {
      window.history.pushState(null, "", `/compare/${job.id}`);
    } else {
      window.history.pushState(null, "", "/");
    }
  };

  useEffect(() => {
    checkBackendStatus();
    setupWebSocket();
  }, []);

  const checkBackendStatus = async () => {
    try {
      const response = await fetch("/health");
      if (response.ok) {
        setBackendStatus("connected");
      } else {
        setBackendStatus("disconnected");
      }
    } catch (error) {
      setBackendStatus("disconnected");
    }
  };

  const setupWebSocket = () => {
    try {
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Dynamic port mapping: 3000 -> 8001, 3001 -> 8002, etc. (port + 5001)
      let wsHost = window.location.host;
      if (window.location.port === "3000" || window.location.port === "3001") {
        const backendPort = parseInt(window.location.port) + 5001;
        wsHost = `127.0.0.1:${backendPort}`;
      }
      const ws = new WebSocket(`${wsProtocol}//${wsHost}/ws/connect`);

      ws.onopen = () => {
        setWsStatus("connected");
        console.log("WebSocket connected");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
        console.log("WebSocket disconnected");
      };

      ws.onerror = () => {
        setWsStatus("disconnected");
      };
    } catch (error) {
      setWsStatus("disconnected");
    }
  };

  const fetchRecentErrors = async () => {
    try {
      const response = await compareApi.getAutomationLogs(0, 10, undefined, true);
      if (response && response.results) {
        setRecentErrors(response.results);
        
        // Oblicz liczbę nieprzeczytanych powiadomień
        const lastReadIdStr = localStorage.getItem("cradle_last_read_error_id");
        const lastReadId = lastReadIdStr ? parseInt(lastReadIdStr, 10) : 0;
        
        const newUnread = response.results.filter((log: any) => log.id > lastReadId).length;
        setUnreadNotifications(newUnread);
      }
    } catch (error) {
      console.error("Failed to fetch recent errors for notifications:", error);
    }
  };

  useEffect(() => {
    // Pierwsze pobranie
    fetchRecentErrors();
    
    // Odpytywanie co 15 sekund
    const interval = setInterval(fetchRecentErrors, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleNotifications = () => {
    setShowNotifications(prev => {
      const nextState = !prev;
      if (nextState && recentErrors.length > 0) {
        // Oznacz wszystkie jako przeczytane
        const maxId = Math.max(...recentErrors.map(log => log.id));
        localStorage.setItem("cradle_last_read_error_id", maxId.toString());
        setUnreadNotifications(0);
      }
      return nextState;
    });
  };

  useEffect(() => {
    if (!showNotifications) return;
    
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".notifications-container")) {
        setShowNotifications(false);
      }
    };
    
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [showNotifications]);

  const getStatusDot = (status: string) => {
    switch (status) {
      case "connected":
        return "bg-green-400";
      case "disconnected":
        return "bg-red-400";
      case "checking":
      default:
        return "bg-yellow-400 animate-pulse";
    }
  };

  // Dynamic runtime check for standalone desktop app mode
  // The macOS wrapper starts the lightweight FastAPI server on port 8005
  // This must be a runtime check because LIVE and Desktop share the same build/ folder!
  const isDesktopMode = window.location.port === "8005";

  if (isDesktopMode) {
    return (
      <div className="min-h-screen bg-slate-50">
        <StandalonePlayer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Navigation Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200 print:hidden">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3 cursor-pointer" onClick={() => { setSelectedJob(null); setDashboardView("list"); }}>
                <div className="p-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">
                    New Video Compare
                  </h1>
                  <p className="text-sm text-gray-500">
                    Professional Video Analysis Platform
                  </p>
                </div>
              </div>
              {/* DEV environment badge — visible only on port 3001 */}
              {window.location.port === "3001" && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-orange-100 text-orange-700 border border-orange-300 animate-pulse" title="Środowisko deweloperskie — zmiany nie wpływają na LIVE">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500 inline-block"></span>
                  DEV
                </span>
              )}
            </div>

            <div className="flex items-center space-x-4">
              {/* Status Indicators */}
              <div className="flex items-center space-x-4 text-sm desktop:flex hidden">
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-2 h-2 rounded-full ${getStatusDot(
                      backendStatus
                    )}`}
                  ></div>
                  <span className="text-gray-600">
                    Backend
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-2 h-2 rounded-full ${getStatusDot(wsStatus)}`}
                  ></div>
                  <span className="text-gray-600">WS</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="h-6 w-px bg-gray-200 mx-2"></div>

              <div className="flex bg-gray-100 p-1 rounded-lg">
                <button
                  onClick={() => { setSelectedJob(null); setDashboardView("list"); }}
                  className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${dashboardView === "list" ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                >
                  <ListBulletIcon className="w-5 h-5 mr-1" />
                  Jobs
                </button>
                <button
                  onClick={() => { setSelectedJob(null); setDashboardView("stats"); }}
                  className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${dashboardView === "stats" ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                >
                  <ChartBarIcon className="w-5 h-5 mr-1" />
                  Stats
                </button>
                <button
                  onClick={() => { setSelectedJob(null); setDashboardView("kb"); }}
                  className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${dashboardView === "kb" ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                >
                  <BookOpenIcon className="w-5 h-5 mr-1" />
                  KB
                </button>
                <button
                  onClick={() => { setSelectedJob(null); setDashboardView("logs"); }}
                  className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${dashboardView === "logs" ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                >
                  <ListBulletIcon className="w-5 h-5 mr-1" />
                  Logs
                </button>
                <button
                  onClick={() => { setSelectedJob(null); setDashboardView("player"); }}
                  className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${dashboardView === "player" ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
                >
                  <PlayIcon className="w-5 h-5 mr-1" />
                  Player
                </button>
              </div>

              <div className="flex items-center space-x-1 border-l border-gray-200 pl-4 ml-2 relative notifications-container">
                <button 
                  onClick={handleToggleNotifications}
                  className={`p-2 focus:outline-none rounded-lg transition-colors relative ${
                    showNotifications ? 'bg-gray-100 text-gray-600' : 'text-gray-400 hover:text-gray-500'
                  }`}
                  title="Powiadomienia systemowe"
                >
                  <BellIcon className="w-5 h-5" />
                  {unreadNotifications > 0 && (
                    <span className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white ring-2 ring-white animate-pulse">
                      {unreadNotifications}
                    </span>
                  )}
                </button>

                {showNotifications && (
                  <div className="absolute right-0 top-full mt-2 w-80 rounded-lg bg-white shadow-xl ring-1 ring-black ring-opacity-5 z-50 overflow-hidden divide-y divide-gray-100">
                    <div className="p-3 bg-gray-50 flex items-center justify-between">
                      <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Błędy Systemowe
                      </span>
                      {recentErrors.length > 0 && (
                        <button 
                          onClick={() => { setSelectedJob(null); setDashboardView("logs"); setShowNotifications(false); }}
                          className="text-xs text-blue-600 hover:text-blue-500 font-medium"
                        >
                          Zobacz logi
                        </button>
                      )}
                    </div>
                    <div className="max-h-80 overflow-y-auto divide-y divide-gray-100">
                      {recentErrors.length === 0 ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          Brak zgłoszonych błędów systemowych.
                        </div>
                      ) : (
                        recentErrors.slice(0, 5).map((log) => (
                          <div 
                            key={log.id} 
                            className="p-3 hover:bg-gray-50 transition-colors cursor-pointer"
                          >
                            <div className="flex items-start justify-between space-x-2">
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-800">
                                {log.component === "desktop_app" ? "Desktop App" : log.component === "extension" ? "Rozszerzenie" : "Backend"}
                              </span>
                              <span className="text-[10px] text-gray-400">
                                {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p className="mt-1 text-xs font-semibold text-gray-900">
                              {log.cradle_id ? `Cradle ID: ${log.cradle_id}` : "Błąd Systemu"}
                            </p>
                            <p className="mt-0.5 text-xs text-gray-600" title={log.message}>
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
            <div className="max-w-7xl mx-auto px-6 py-4">
              <nav className="flex" aria-label="Breadcrumb">
                <ol className="flex items-center space-x-4">
                  <li>
                    <button
                      onClick={() => handleSelectJob(null)}
                      className="text-blue-600 hover:text-blue-500 font-medium transition-colors"
                    >
                      Dashboard
                    </button>
                  </li>
                  <li>
                    <div className="flex items-center">
                      <svg
                        className="flex-shrink-0 h-5 w-5 text-gray-400"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="ml-4 text-gray-500 font-medium">
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
            />
          </div>
        ) : dashboardView === "kb" ? (
          <KnowledgeBase onSelectJob={handleSelectJob} />
        ) : dashboardView === "logs" ? (
          <AutomationLogs />
        ) : dashboardView === "player" ? (
          <StandalonePlayer />
        ) : (
          <Dashboard onSelectJob={handleSelectJob} viewMode={dashboardView as "list" | "stats"} />
        )}
      </div>

      {/* Auto-Pair Modal */}
      {showAutoPair && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-xl bg-white">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                Create Auto-Pair Job
              </h3>
              <button
                onClick={() => setShowAutoPair(false)}
                className="text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded-lg p-1 transition-colors"
              >
                <svg
                  className="w-6 h-6"
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
