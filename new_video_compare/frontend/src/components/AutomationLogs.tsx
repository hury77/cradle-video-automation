import React, { useState, useEffect } from "react";
import { compareApi, AutomationLog } from "../services/api";
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  ArrowPathIcon
} from "@heroicons/react/24/outline";
import { translations, Language } from "../utils/translations";

interface AutomationLogsProps {
  lang?: Language;
  theme?: "dark" | "light";
}

export default function AutomationLogs({ lang = "PL", theme = "dark" }: AutomationLogsProps) {
  const t = translations[lang];
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [page, setPage] = useState(1);
  const [componentFilter, setComponentFilter] = useState<string>("");
  const [onlyErrors, setOnlyErrors] = useState<boolean>(false);
  const [cradleIdSearch, setCradleIdSearch] = useState<string>("");
  const [availableComponents, setAvailableComponents] = useState<string[]>([]);
  
  const limit = 50;

  useEffect(() => {
    fetchLogs();
  }, [page, componentFilter, onlyErrors, cradleIdSearch]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const skip = (page - 1) * limit;
      const response = await compareApi.getAutomationLogs(
        skip,
        limit,
        componentFilter || undefined,
        onlyErrors,
        cradleIdSearch || undefined
      );
      setLogs(response.results);
      setTotal(response.total);
      setAvailableComponents(response.components || []);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 transition-colors">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-white">Automation Logs</h2>
          <p className="mt-1 text-sm font-semibold text-slate-500 dark:text-slate-400">
            System health and events from Desktop App and Chrome Extension
          </p>
        </div>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 border border-slate-200 dark:border-white/10 text-xs font-bold rounded-xl text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm"
        >
          <ArrowPathIcon className={`w-4 h-4 mr-2 ${loading ? 'animate-spin cursor-not-allowed' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-[#161824] rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 p-5 mb-6 transition-colors">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-4 w-4 text-slate-400" />
            </div>
            <input
              type="text"
              placeholder="Search by Cradle ID..."
              value={cradleIdSearch}
              onChange={(e) => {
                setCradleIdSearch(e.target.value);
                setPage(1);
              }}
              className="block w-full pl-9 pr-3 py-2 border border-slate-200 dark:border-white/10 rounded-xl bg-slate-50 dark:bg-[#12131c] text-slate-900 dark:text-white placeholder-slate-400 text-xs font-bold focus:ring-indigo-500"
            />
          </div>

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <FunnelIcon className="h-4 w-4 text-slate-400" />
            </div>
            <select
              value={componentFilter}
              onChange={(e) => {
                setComponentFilter(e.target.value);
                setPage(1);
              }}
              className="block w-full pl-9 pr-8 py-2 border border-slate-200 dark:border-white/10 rounded-xl bg-slate-50 dark:bg-[#12131c] text-slate-900 dark:text-white text-xs font-bold appearance-none focus:ring-indigo-500"
            >
              <option value="" className="dark:bg-[#161824]">All Components</option>
              {availableComponents.map((comp) => (
                <option key={comp} value={comp} className="dark:bg-[#161824]">
                  {comp}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyErrors}
                onChange={(e) => {
                  setOnlyErrors(e.target.checked);
                  setPage(1);
                }}
                className="w-4 h-4 text-rose-600 focus:ring-rose-500 border-slate-300 rounded transition-colors"
              />
              <span className="text-xs font-extrabold text-slate-700 dark:text-slate-200 select-none">Show Errors Only</span>
            </label>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-white dark:bg-[#161824] rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 overflow-hidden transition-colors">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-100 dark:divide-white/5">
            <thead className="bg-slate-100 dark:bg-slate-800/80">
              <tr>
                <th scope="col" className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Time
                </th>
                <th scope="col" className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Type
                </th>
                <th scope="col" className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Component / Action
                </th>
                <th scope="col" className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Message
                </th>
                <th scope="col" className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Cradle ID
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-[#161824] divide-y divide-slate-100 dark:divide-white/5">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 dark:border-cyan-400"></div>
                    <p className="mt-2 text-xs font-bold text-slate-400">Loading logs...</p>
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-xs font-bold text-slate-400">
                    No logs found matching your filters.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors ${log.is_error ? 'bg-rose-50/50 dark:bg-rose-950/20' : ''}`}>
                    <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-slate-500 dark:text-slate-400 truncate max-w-xs">
                      {new Date(log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z').toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {log.is_error ? (
                        <div className="flex items-center text-rose-600 dark:text-rose-400">
                          <ExclamationCircleIcon className="w-4 h-4 mr-1.5" />
                          <span className="text-xs font-black">Error</span>
                        </div>
                      ) : (
                        <div className="flex items-center text-indigo-600 dark:text-cyan-400">
                          <InformationCircleIcon className="w-4 h-4 mr-1.5" />
                          <span className="text-xs font-black">Info</span>
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="text-xs font-black text-slate-900 dark:text-white">{log.component}</span>
                        <span className="text-[11px] font-semibold text-slate-400">{log.action}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs font-medium text-slate-900 dark:text-slate-200">
                       <div className="line-clamp-2" title={log.message}>{log.message}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {log.cradle_id ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {log.cradle_id}
                        </span>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-white px-4 py-3 border-t border-gray-200 flex items-center justify-between sm:px-6">
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Showing <span className="font-medium">{(page - 1) * limit + 1}</span> to{" "}
                  <span className="font-medium">
                    {Math.min(page * limit, total)}
                  </span>{" "}
                  of <span className="font-medium">{total}</span> results
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className={`relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium ${
                      page === 1 ? 'text-gray-300 cursor-not-allowed' : 'text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    Previous
                  </button>
                  {[...Array(totalPages)].map((_, i) => {
                    // Show max 5 pages around current
                    if (
                      i + 1 === 1 ||
                      i + 1 === totalPages ||
                      Math.abs(page - (i + 1)) <= 1
                    ) {
                      return (
                        <button
                          key={i + 1}
                          onClick={() => setPage(i + 1)}
                          className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                            page === i + 1
                              ? 'z-10 bg-blue-50 border-blue-500 text-blue-600'
                              : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                          }`}
                        >
                          {i + 1}
                        </button>
                      );
                    } else if (
                      i + 1 === page - 2 ||
                      i + 1 === page + 2
                    ) {
                      return <span key={i + 1} className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">...</span>
                    }
                    return null;
                  })}
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className={`relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium ${
                      page === totalPages ? 'text-gray-300 cursor-not-allowed' : 'text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    Next
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
