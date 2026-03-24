import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { BookOpenIcon, FunnelIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";

export interface QADecision {
  id: number;
  job_id: number;
  job_name: string | null;
  verdict: "approve" | "reject" | "review";
  reasoning: string | null;
  client_name: string | null;
  cradle_id: string | null;
  decided_by: string;
  metrics_snapshot: any;
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
    <div className="min-h-screen bg-slate-50 p-6">
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
                        <button
                          onClick={() => onSelectJob({ id: d.job_id })}
                          className="text-blue-600 hover:text-blue-900 bg-blue-50 px-3 py-1.5 rounded-md hover:bg-blue-100 transition"
                        >
                          View Job
                        </button>
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
