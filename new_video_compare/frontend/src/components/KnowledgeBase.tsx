import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { BookOpenIcon, FunnelIcon, MagnifyingGlassIcon, ArrowDownTrayIcon, DocumentTextIcon, CodeBracketIcon } from "@heroicons/react/24/outline";

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

const KnowledgeBase: React.FC<{ onSelectJob: (job: any) => void }> = ({ onSelectJob }) => {
  const [decisions, setDecisions] = useState<QADecision[]>([]);
  const [clients, setClients] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [filters, setFilters] = useState({
    client_name: "",
    verdict: "",
  });

  const [selectedDecisionDetails, setSelectedDecisionDetails] = useState<QADecision | null>(null);

  const fetchKnowledgeBase = async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (filters.client_name) query.append("client_name", filters.client_name);
      if (filters.verdict) query.append("verdict", filters.verdict);

      const res = await fetch(`/api/v1/dashboard/knowledge-base?${query.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setDecisions(data.results);
      setClients(data.clients);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
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
    fetchKnowledgeBase();
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
    <div className="min-h-screen bg-slate-50 p-6 relative">
      {/* Existing modal overlay */}
      {selectedDecisionDetails && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
              <h2 className="text-lg font-bold text-gray-900">Archived AI Knowledge Snapshot</h2>
              <button 
                onClick={() => setSelectedDecisionDetails(null)}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <span className="sr-only">Close</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1 h-full font-mono text-sm leading-relaxed text-gray-700 space-y-4">
               <div>
                  <h3 className="font-semibold text-gray-900 uppercase tracking-wide text-xs mb-2">Verdict</h3>
                  <div className={`inline-block px-3 py-1 rounded-md border font-bold uppercase text-xs ${getVerdictStyle(selectedDecisionDetails.verdict)}`}>
                    {selectedDecisionDetails.verdict}
                  </div>
               </div>
               <div>
                  <h3 className="font-semibold text-gray-900 uppercase tracking-wide text-xs mb-2">AI Expert Reasoning</h3>
                  <div className="bg-gray-50 border border-gray-200 p-4 rounded-lg whitespace-pre-wrap">
                    {selectedDecisionDetails.ai_reasoning || selectedDecisionDetails.reasoning || "No reasoning captured."}
                  </div>
               </div>
               <div>
                  <h3 className="font-semibold text-gray-900 uppercase tracking-wide text-xs mb-2">Knowledge Base Snapshot (JSON)</h3>
                  <div className="bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto whitespace-pre">
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
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <div className="p-2 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg shadow-sm">
                <BookOpenIcon className="w-6 h-6 text-white" />
              </div>
              QA Knowledge Base
            </h1>
            <p className="text-gray-500 mt-1 ml-14">
              Historical QA decisions for Agent 2 training.
            </p>
          </div>
          <button onClick={fetchKnowledgeBase} className="text-sm text-blue-600 hover:underline">
            Refresh Data
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6 flex gap-4 items-center">
          <div className="flex items-center text-gray-500 font-medium">
            <FunnelIcon className="w-5 h-5 mr-2" /> Filters:
          </div>
          
          <select
            value={filters.client_name}
            onChange={e => setFilters(f => ({ ...f, client_name: e.target.value }))}
            className="border-gray-300 rounded-lg text-sm focus:ring-blue-500 py-2 pl-3 pr-8 min-w-[200px]"
          >
            <option value="">All Clients</option>
            {clients.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          <select
            value={filters.verdict}
            onChange={e => setFilters(f => ({ ...f, verdict: e.target.value }))}
            className="border-gray-300 rounded-lg text-sm focus:ring-blue-500 py-2 pl-3 pr-8 min-w-[150px]"
          >
            <option value="">All Verdicts</option>
            <option value="approve">Approve</option>
            <option value="reject">Reject</option>
            <option value="review">Review</option>
          </select>

          <div className="flex-grow"></div>

          <div className="flex gap-2">
            <button
              onClick={() => handleExport('csv')}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
              CSV
            </button>
            <button
              onClick={() => handleExport('json')}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              title="Full export for AI Training Model"
            >
              <CodeBracketIcon className="w-4 h-4 mr-2" />
              JSON
            </button>
            <button
              onClick={() => handleExport('pdf')}
              className="inline-flex items-center px-4 py-2 border border-blue-600 shadow-sm text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              <DocumentTextIcon className="w-4 h-4 mr-2" />
              PDF
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-gray-500">Loading Knowledge Base...</div>
          ) : decisions.length === 0 ? (
            <div className="p-12 text-center text-gray-500">No QA decisions found matching the filters.</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Job ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cradle ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Verdict</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reasoning</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metrics</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {decisions.map(d => {
                  const m = d.metrics_snapshot || {};
                  return (
                    <tr key={d.id} className="hover:bg-gray-50 transition">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-500">
                        {d.job_id ? `#${d.job_id}` : <span className="text-gray-300 italic">Deleted</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {d.cradle_id || "N/A"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-semibold">
                        {d.client_name || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full border uppercase tracking-wider ${getVerdictStyle(d.verdict)}`}>
                          {d.verdict}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 max-w-md truncate" title={d.reasoning || ""}>
                        {d.reasoning || <span className="text-gray-400 italic">No reasoning provided</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500 font-mono">
                        V: {m.video_similarity ? Math.round(m.video_similarity * 100) + '%' : '-'} | 
                        A: {m.audio_similarity ? Math.round(m.audio_similarity * 100) + '%' : '-'} | 
                        O: {m.overall_similarity ? Math.round(m.overall_similarity * 100) + '%' : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(d.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
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
                            className="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md hover:bg-blue-100 transition"
                          >
                            View Job
                          </button>
                        ) : (
                          <button
                            onClick={() => setSelectedDecisionDetails(d)}
                            className="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1.5 rounded-md hover:bg-indigo-100 transition whitespace-nowrap border border-indigo-100 shadow-sm font-semibold flex items-center justify-center gap-1 mx-auto"
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
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBase;
