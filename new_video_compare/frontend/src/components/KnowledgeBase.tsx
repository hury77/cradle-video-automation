import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { BookOpenIcon, FunnelIcon, MagnifyingGlassIcon, ArrowDownTrayIcon, DocumentTextIcon, CodeBracketIcon } from "@heroicons/react/24/outline";

import { translations, Language } from "../utils/translations";

export interface QADecision {
  id: number;
  job_id: number;
  job_name: string | null;
  verdict: "approve" | "reject" | "review";
  reasoning: string | null;
  ai_reasoning: string | null;
  client_name: string | null;
  cradle_id: string | null;
  decided_by: string;
  metrics_snapshot: any;
  knowledge_snapshot: any;
  created_at: string;
}

interface KnowledgeBaseProps {
  onSelectJob: (job: any) => void;
  lang?: Language;
  theme?: "dark" | "light";
}

const KnowledgeBase: React.FC<KnowledgeBaseProps> = ({ onSelectJob, lang = "PL", theme = "dark" }) => {
  const t = translations[lang];
  const [decisions, setDecisions] = useState<QADecision[]>([]);
  const [clients, setClients] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalEntries, setTotalEntries] = useState(0);
  const [pageInput, setPageInput] = useState("1");
  const limit = 50;
  
  const [filters, setFilters] = useState({
    client_name: "",
    verdict: "",
  });

  const [selectedDecisionDetails, setSelectedDecisionDetails] = useState<QADecision | null>(null);

  const fetchKnowledgeBase = async (page: number) => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (filters.client_name) query.append("client_name", filters.client_name);
      if (filters.verdict) query.append("verdict", filters.verdict);
      
      const skip = (page - 1) * limit;
      query.append("skip", skip.toString());
      query.append("limit", limit.toString());

      const res = await fetch(`/api/v1/dashboard/knowledge-base?${query.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setDecisions(data.results);
      setClients(data.clients);
      setTotalEntries(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    setPageInput(newPage.toString());
    fetchKnowledgeBase(newPage);
  };

  const handleJumpToPage = () => {
    const pageNum = parseInt(pageInput, 10);
    const maxPage = Math.max(1, Math.ceil(totalEntries / limit));
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= maxPage) {
      handlePageChange(pageNum);
    } else {
      alert(`Wprowadź poprawny numer strony od 1 do ${maxPage}.`);
      setPageInput(currentPage.toString());
    }
  };

  const handleExport = async (format: 'csv' | 'pdf' | 'json') => {
    try {
      const query = new URLSearchParams();
      if (filters.client_name) query.append("client_name", filters.client_name);
      if (filters.verdict) query.append("verdict", filters.verdict);
      
      const response = await fetch(`/api/v1/dashboard/kb/export/${format}?${query.toString()}`);
      if (!response.ok) throw new Error("Export failed");
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cradle_kb_export_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e) {
      console.error(e);
      alert("Failed to export knowledge base.");
    }
  };

  useEffect(() => {
    setCurrentPage(1);
    setPageInput("1");
    fetchKnowledgeBase(1);
  }, [filters]);

  const getVerdictStyle = (v: string) => {
    switch (v) {
      case "approve": return "bg-green-100 text-green-800 border-green-200";
      case "reject": return "bg-red-100 text-red-800 border-red-200";
      case "review": return "bg-amber-100 text-amber-800 border-amber-200";
      default: return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0d0e15] text-slate-900 dark:text-slate-100 p-6 relative transition-colors">
      {/* Existing modal overlay */}
      {selectedDecisionDetails && (
        <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-[#161824] border border-slate-200 dark:border-white/10 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-white/10 flex justify-between items-center bg-slate-50 dark:bg-slate-800/50">
              <h2 className="text-lg font-black text-slate-900 dark:text-white">Archived AI Knowledge Snapshot</h2>
              <button 
                onClick={() => setSelectedDecisionDetails(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white focus:outline-none"
              >
                <span className="sr-only">Close</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1 h-full font-mono text-sm leading-relaxed text-slate-700 dark:text-slate-300 space-y-4">
               <div>
                  <h3 className="font-bold text-slate-900 dark:text-white uppercase tracking-wide text-xs mb-2">Verdict</h3>
                  <div className={`inline-block px-3 py-1 rounded-md border font-bold uppercase text-xs ${getVerdictStyle(selectedDecisionDetails.verdict)}`}>
                    {selectedDecisionDetails.verdict}
                  </div>
               </div>
               <div>
                  <h3 className="font-bold text-slate-900 dark:text-white uppercase tracking-wide text-xs mb-2">AI Expert Reasoning</h3>
                  <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-white/10 p-4 rounded-xl whitespace-pre-wrap font-sans text-xs">
                    {selectedDecisionDetails.ai_reasoning || selectedDecisionDetails.reasoning || "No reasoning captured."}
                  </div>
               </div>
               <div>
                  <h3 className="font-bold text-slate-900 dark:text-white uppercase tracking-wide text-xs mb-2">Knowledge Base Snapshot (JSON)</h3>
                  <div className="bg-slate-950 text-cyan-400 p-4 rounded-xl overflow-x-auto whitespace-pre font-mono text-xs border border-white/5">
                    {selectedDecisionDetails.knowledge_snapshot ? JSON.stringify(selectedDecisionDetails.knowledge_snapshot, null, 2) : "Snapshot data not available for this legacy request."}
                  </div>
               </div>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-[1600px] mx-auto">
        <div className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white flex items-center gap-3">
              <div className="p-2.5 bg-gradient-to-r from-[#350F9C] to-[#4960E6] rounded-xl shadow-md">
                <BookOpenIcon className="w-6 h-6 text-white" />
              </div>
              QA Knowledge Base
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1 ml-14 font-semibold text-sm">
              Historical QA decisions for Agent 2 training.
            </p>
          </div>
          <button onClick={() => fetchKnowledgeBase(currentPage)} className="text-xs font-bold text-indigo-600 dark:text-cyan-400 hover:underline">
            Refresh Data
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-[#161824] rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 p-5 mb-6 flex flex-wrap gap-4 items-center transition-colors">
          <div className="flex items-center text-slate-500 dark:text-slate-400 font-bold text-xs uppercase tracking-wider">
            <FunnelIcon className="w-4 h-4 mr-2 text-slate-400" /> Filters:
          </div>
          
          <select
            value={filters.client_name}
            onChange={e => setFilters(f => ({ ...f, client_name: e.target.value }))}
            className="bg-slate-50 dark:bg-[#12131c] border-slate-200 dark:border-white/10 text-slate-900 dark:text-slate-100 rounded-xl text-xs font-bold focus:ring-indigo-500 py-2 pl-3 pr-8 min-w-[200px]"
          >
            <option value="" className="dark:bg-[#161824]">All Clients</option>
            {clients.map(c => <option key={c} value={c} className="dark:bg-[#161824]">{c}</option>)}
          </select>

          <select
            value={filters.verdict}
            onChange={e => setFilters(f => ({ ...f, verdict: e.target.value }))}
            className="bg-slate-50 dark:bg-[#12131c] border-slate-200 dark:border-white/10 text-slate-900 dark:text-slate-100 rounded-xl text-xs font-bold focus:ring-indigo-500 py-2 pl-3 pr-8 min-w-[150px]"
          >
            <option value="" className="dark:bg-[#161824]">All Verdicts</option>
            <option value="approve" className="dark:bg-[#161824]">Approve</option>
            <option value="reject" className="dark:bg-[#161824]">Reject</option>
            <option value="review" className="dark:bg-[#161824]">Review</option>
          </select>

          <div className="flex-grow"></div>

          <div className="flex gap-2">
            <button
              onClick={() => handleExport('csv')}
              className="inline-flex items-center px-3.5 py-1.5 border border-slate-200 dark:border-white/10 shadow-sm text-xs font-bold rounded-xl text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-1.5" />
              CSV
            </button>
            <button
              onClick={() => handleExport('json')}
              className="inline-flex items-center px-3.5 py-1.5 border border-slate-200 dark:border-white/10 shadow-sm text-xs font-bold rounded-xl text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              title="Full export for AI Training Model"
            >
              <CodeBracketIcon className="w-4 h-4 mr-1.5" />
              JSON
            </button>
            <button
              onClick={() => handleExport('pdf')}
              className="inline-flex items-center px-3.5 py-1.5 border border-transparent shadow-md text-xs font-bold rounded-xl text-white bg-gradient-to-r from-[#350F9C] to-[#4960E6] hover:opacity-90 transition-opacity"
            >
              <DocumentTextIcon className="w-4 h-4 mr-1.5" />
              PDF
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white dark:bg-[#161824] rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 overflow-hidden transition-colors">
          {loading ? (
            <div className="p-12 text-center text-slate-400 font-bold text-sm">Loading Knowledge Base...</div>
          ) : decisions.length === 0 ? (
            <div className="p-12 text-center text-slate-400 font-bold text-sm">No QA decisions found matching the filters.</div>
          ) : (
            <>
              <table className="min-w-full divide-y divide-slate-100 dark:divide-white/5">
                <thead className="bg-slate-100 dark:bg-slate-800/80">
                  <tr>
                    <th className="px-6 py-3.5 text-left text-xs font-extrabold text-slate-500 dark:text-slate-400 uppercase">Job ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cradle ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Verdict</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reasoning</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metrics</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Action</th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-[#161824] divide-y divide-slate-100 dark:divide-white/5">
                  {decisions.map(d => {
                    const m = d.metrics_snapshot || {};
                    return (
                      <tr key={d.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-slate-500 dark:text-slate-400">
                          {d.job_id ? `#${d.job_id}` : <span className="text-slate-400 dark:text-slate-500 italic">Deleted</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-slate-900 dark:text-white">
                          {d.cradle_id || "N/A"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-700 dark:text-slate-300 font-semibold">
                          {d.client_name || "-"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs">
                          <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-black rounded-full border uppercase tracking-wider ${getVerdictStyle(d.verdict)}`}>
                            {d.verdict}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-xs font-medium text-slate-600 dark:text-slate-300 max-w-md truncate" title={d.reasoning || ""}>
                          {d.reasoning || <span className="text-slate-400 italic">No reasoning provided</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-500 dark:text-slate-400 font-mono">
                          V: {m.video_similarity ? Math.round(m.video_similarity * 100) + '%' : '-'} | 
                          A: {m.audio_similarity ? Math.round(m.audio_similarity * 100) + '%' : '-'} | 
                          O: {m.overall_similarity ? Math.round(m.overall_similarity * 100) + '%' : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-500 dark:text-slate-400 font-medium">
                          {new Date(d.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center text-xs font-bold">
                          {d.job_id ? (
                            <button
                              onClick={async () => {
                                try {
                                  // Fetch full job to populate VideoComparison props
                                  const res = await fetch(`/api/v1/compare/${d.job_id}`);
                                  if (res.ok) {
                                    const jobData = await res.json();
                                    onSelectJob(jobData);
                                  } else {
                                    alert('The Job and its files have been deleted from the database.');
                                  }
                                } catch (e) {
                                  console.error(e);
                                }
                              }}
                              className="text-indigo-600 dark:text-cyan-400 hover:text-indigo-900 bg-indigo-50 dark:bg-slate-800 border border-indigo-100 dark:border-white/10 px-3 py-1.5 rounded-xl hover:bg-indigo-100 dark:hover:bg-slate-700 transition"
                            >
                              View Job
                            </button>
                          ) : (
                            <button
                              onClick={() => setSelectedDecisionDetails(d)}
                              className="text-indigo-600 dark:text-cyan-400 bg-indigo-50 dark:bg-slate-800 border border-indigo-100 dark:border-white/10 px-3 py-1.5 rounded-xl hover:bg-indigo-100 dark:hover:bg-slate-700 transition whitespace-nowrap shadow-sm font-bold flex items-center justify-center gap-1 mx-auto"
                              title="View extracted reasoning & metrics for this deleted job"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                              AI Details
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Pagination Controls */}
              <div className="px-6 py-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-white/10 flex items-center justify-between flex-wrap gap-4">
                <div className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  Pokazywanie <span className="font-extrabold text-slate-900 dark:text-white">{Math.min((currentPage - 1) * limit + 1, totalEntries)}</span> do{" "}
                  <span className="font-extrabold text-slate-900 dark:text-white">{Math.min(currentPage * limit, totalEntries)}</span> z{" "}
                  <span className="font-extrabold text-slate-900 dark:text-white">{totalEntries}</span> wpisów
                </div>
                <div className="flex items-center space-x-2 flex-wrap gap-2">
                  <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="px-3.5 py-1.5 border border-slate-200 dark:border-white/10 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    Poprzednia
                  </button>
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-bold px-2">
                    Strona {currentPage} z {Math.max(1, Math.ceil(totalEntries / limit))}
                  </span>
                  <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage >= Math.ceil(totalEntries / limit)}
                    className="px-3.5 py-1.5 border border-slate-200 dark:border-white/10 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    Następna
                  </button>

                  <div className="h-6 w-px bg-gray-200 mx-2 hidden sm:block"></div>

                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <span>Idź do:</span>
                    <input
                      type="number"
                      min="1"
                      max={Math.max(1, Math.ceil(totalEntries / limit))}
                      value={pageInput}
                      onChange={(e) => setPageInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleJumpToPage();
                        }
                      }}
                      className="w-16 px-2.5 py-1.5 border border-gray-300 rounded-lg text-center text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none"
                    />
                    <button
                      onClick={handleJumpToPage}
                      className="px-3 py-1.5 bg-white hover:bg-gray-50 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 shadow-sm transition"
                    >
                      Idź
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBase;
