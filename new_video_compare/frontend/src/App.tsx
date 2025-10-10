// frontend/src/App.tsx
import React, { useState, useEffect } from "react";
import Dashboard from "./components/Dashboard";
import VideoComparison from "./components/VideoComparison";
import AutoPairForm from "./components/AutoPairForm";
import { ComparisonJob } from "./types";
import {
  Cog6ToothIcon,
  BellIcon,
  UserIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";

function App() {
  const [selectedJob, setSelectedJob] = useState<ComparisonJob | null>(null);
  const [showAutoPair, setShowAutoPair] = useState(false);
  const [backendStatus, setBackendStatus] = useState<
    "connected" | "disconnected" | "checking"
  >("checking");
  const [wsStatus, setWsStatus] = useState<
    "connected" | "disconnected" | "checking"
  >("checking");

  useEffect(() => {
    checkBackendStatus();
    setupWebSocket();
  }, []);

  const checkBackendStatus = async () => {
    try {
      const response = await fetch("http://localhost:8001/health");
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
      const ws = new WebSocket("ws://localhost:8001/ws");

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Navigation Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
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
            </div>

            <div className="flex items-center space-x-4">
              {/* Status Indicators */}
              <div className="flex items-center space-x-4 text-sm">
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-2 h-2 rounded-full ${getStatusDot(
                      backendStatus
                    )}`}
                  ></div>
                  <span className="text-gray-600">
                    Backend: {backendStatus}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-2 h-2 rounded-full ${getStatusDot(wsStatus)}`}
                  ></div>
                  <span className="text-gray-600">WebSocket: {wsStatus}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <button
                onClick={() => setShowAutoPair(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200 shadow-sm hover:shadow-md"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Auto-Pair Job
              </button>

              <div className="flex items-center space-x-2">
                <button className="p-2 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded-lg transition-colors">
                  <BellIcon className="w-5 h-5" />
                </button>
                <button className="p-2 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded-lg transition-colors">
                  <Cog6ToothIcon className="w-5 h-5" />
                </button>
                <button className="p-2 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded-lg transition-colors">
                  <UserIcon className="w-5 h-5" />
                </button>
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
                      onClick={() => setSelectedJob(null)}
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
            <VideoComparison job={selectedJob} />
          </div>
        ) : (
          <Dashboard onSelectJob={setSelectedJob} />
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
