// frontend/src/components/Dashboard.tsx
import React, { useState, useEffect } from "react";
import {
  PlayIcon,
  PauseIcon,
  TrashIcon,
  EyeIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  SparklesIcon,
  FilmIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  CircleStackIcon,
  ChartBarIcon,
  UserGroupIcon,
  BoltIcon
} from "@heroicons/react/24/outline";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';

import { ComparisonJob } from "../types";
import { compareApi, DashboardStats } from "../services/api";
import FileUpload from "./FileUpload";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const JobTimer: React.FC<{ startedAt?: string }> = ({ startedAt }) => {
  const [elapsed, setElapsed] = useState<number>(0);

  useEffect(() => {
    if (!startedAt) return;
    const dateStr = startedAt.endsWith('Z') || startedAt.includes('+') ? startedAt : `${startedAt}Z`;
    const start = new Date(dateStr).getTime();
    setElapsed(Math.max(0, Date.now() - start));
    const interval = setInterval(() => setElapsed(Math.max(0, Date.now() - start)), 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  const formatElapsed = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return <span className="font-mono text-xs text-blue-600 font-medium">{formatElapsed(elapsed)}</span>;
};

interface DashboardProps {
  onSelectJob: (job: ComparisonJob) => void;
  viewMode: 'list' | 'stats' | 'kb';
}

const Dashboard: React.FC<DashboardProps> = ({ onSelectJob, viewMode }) => {
  const [jobs, setJobs] = useState<ComparisonJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [cradleIdFilter, setCradleIdFilter] = useState<string>("");
  const [clientFilter, setClientFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => fetchJobs(true), 30000); // Background refresh
    return () => clearInterval(interval);
  }, [statusFilter, cradleIdFilter, clientFilter, typeFilter]);

  const fetchJobs = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);

      const [jobsResponse, statsResponse] = await Promise.all([
        compareApi.getJobs({
          status: statusFilter || undefined,
          cradleId: cradleIdFilter || undefined,
          clientName: clientFilter || undefined,
          comparisonType: typeFilter || undefined,
          limit: 50
        }),
        compareApi.getDashboardStats().catch(err => null)
      ]);
      
      setJobs(jobsResponse);
      if (statsResponse) setDashboardStats(statsResponse);
      
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  const handleStartJob = async (jobId: number) => {
    try {
      await compareApi.startJob(jobId);
      fetchJobs();
    } catch (error) {
      console.error("Failed to start job:", error);
    }
  };

  const handleStopJob = async (jobId: number) => {
    try {
      await compareApi.cancelJob(jobId);
      fetchJobs();
    } catch (error) {
      console.error("Failed to stop job:", error);
    }
  };

  const handleRetryJob = async (jobId: number) => {
    try {
      await compareApi.retryJob(jobId);
      fetchJobs();
    } catch (error) {
      console.error("Failed to retry job:", error);
      alert("Failed to retry job. Check console for details.");
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    if (!window.confirm("Are you sure you want to delete this job?")) return;
    try {
      await compareApi.deleteJob(jobId);
      fetchJobs();
    } catch (error) {
      console.error("Failed to delete job:", error);
    }
  };

  const handleCleanup = async () => {
    const daysStr = window.prompt("Delete jobs and files older than how many days?", "14");
    if (daysStr === null) return;
    const days = parseInt(daysStr, 10);
    if (isNaN(days)) return;

    if (!window.confirm(`Are you sure you want to delete ALL jobs and associated files older than ${days} days?`)) return;
    
    setCleaningUp(true);
    try {
      const result = await compareApi.cleanupOldJobs(days, 100);
      alert(`Cleanup complete!\n${result.message}\nFreed: ${result.freed_space_mb} MB`);
      fetchJobs();
    } catch (error) {
      alert("Cleanup failed.");
    } finally {
      setCleaningUp(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
      case "processing": return <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin" />;
      case "completed": return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case "failed": return <XCircleIcon className="w-5 h-5 text-red-500" />;
      default: return <ClockIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
    switch (status) {
      case "pending":
      case "processing": return `${base} bg-blue-100 text-blue-800`;
      case "completed": return `${base} bg-green-100 text-green-800`;
      case "failed": return `${base} bg-red-100 text-red-800`;
      default: return `${base} bg-gray-100 text-gray-800`;
    }
  };

  const MetricBadge: React.FC<{ label: string; value?: number }> = ({ label, value }) => {
    if (value === undefined || value === null) return null;
    const score = Math.round(value * 100);
    let bgColor = "bg-gray-100 text-gray-600";
    if (score >= 95) bgColor = "bg-emerald-100 text-emerald-700 border-emerald-200";
    else if (score >= 85) bgColor = "bg-amber-100 text-amber-700 border-amber-200";
    else bgColor = "bg-rose-100 text-rose-700 border-rose-200";

    return (
      <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded border text-[10px] font-bold ${bgColor} uppercase tracking-tight`}>
        <span className="opacity-60">{label}:</span>
        <span>{score}%</span>
      </div>
    );
  };

  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();
  const formatDuration = (seconds?: number) => (seconds === undefined || seconds === null) ? "-" : `${seconds.toFixed(2)}s`;

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center">
            <div className="h-4 w-32 bg-gray-200 rounded mb-4"></div>
            <div className="text-gray-400">Loading Dashboard...</div>
        </div>
      </div>
    );
  }

  // View: Stats (Dashboard)
  if (viewMode === 'stats') {
      return (
        <div className="min-h-screen bg-slate-50 p-6">
          <div className="max-w-[1600px] mx-auto">
            {/* Header */}
            <div className="mb-8 flex justify-between items-end">
              <div>
                <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                  <div className="p-2 bg-blue-600 rounded-lg shadow-sm">
                     <ChartBarIcon className="w-6 h-6 text-white" />
                  </div>
                  System Statistics
                </h1>
                <p className="text-gray-500 mt-1 ml-14">Analytics and Performance Metrics</p>
              </div>
              <button onClick={() => fetchJobs()} className="text-sm text-blue-600 hover:underline">Refresh Data</button>
            </div>
    
            {/* KPI Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                {/* KPI 1: Success Rate */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500">Success Rate</p>
                            <h3 className="text-2xl font-bold text-gray-900 mt-1">
                                {dashboardStats?.kpi.success_rate}%
                            </h3>
                        </div>
                        <div className="p-2 bg-green-50 rounded-lg">
                            <ChartBarIcon className="w-5 h-5 text-green-600" />
                        </div>
                    </div>
                    <div className="mt-4 text-xs text-green-600 font-medium">
                        {dashboardStats?.breakdown.completed} Completed / {dashboardStats?.breakdown.failed} Failed
                    </div>
                </div>
    
                {/* KPI 2: Throughput 24h */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500">24h Throughput</p>
                            <h3 className="text-2xl font-bold text-gray-900 mt-1">
                                {dashboardStats?.kpi.throughput_24h}
                            </h3>
                        </div>
                        <div className="p-2 bg-purple-50 rounded-lg">
                            <BoltIcon className="w-5 h-5 text-purple-600" />
                        </div>
                    </div>
                     <div className="mt-4 text-xs text-purple-600 font-medium">
                        Jobs processed in last 24h
                    </div>
                </div>
    
                {/* KPI 3: Avg Processing Time */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500">Avg Processing Time</p>
                            <h3 className="text-2xl font-bold text-gray-900 mt-1">
                                {dashboardStats?.kpi.avg_processing_time}s
                            </h3>
                        </div>
                        <div className="p-2 bg-blue-50 rounded-lg">
                            <ClockIcon className="w-5 h-5 text-blue-600" />
                        </div>
                    </div>
                     <div className="mt-4 text-xs text-blue-600 font-medium">
                        Per completed job
                    </div>
                </div>
    
                {/* KPI 4: Active Jobs */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500">Active Queue</p>
                            <h3 className="text-2xl font-bold text-gray-900 mt-1">
                                {dashboardStats?.kpi.active_jobs}
                            </h3>
                        </div>
                        <div className={`p-2 rounded-lg ${dashboardStats?.kpi.active_jobs ? 'bg-amber-50' : 'bg-gray-50'}`}>
                            <ArrowPathIcon className={`w-5 h-5 ${dashboardStats?.kpi.active_jobs ? 'text-amber-600 animate-spin' : 'text-gray-400'}`} />
                        </div>
                    </div>
                     <div className="mt-4 text-xs text-gray-500">
                        Jobs pending or processing
                    </div>
                </div>
            </div>
    
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                {/* Trend Chart (Last 7 Days) */}
                <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                     <div className="flex items-center gap-2 mb-6">
                        <ChartBarIcon className="w-5 h-5 text-gray-400" />
                        <h3 className="font-semibold text-gray-900">Job Trend (Last 7 Days)</h3>
                     </div>
                     <div className="h-64 w-full">
                        {dashboardStats?.chart_data ? (
                            <Line
                                data={{
                                    labels: dashboardStats.chart_data.map(d => {
                                        const date = new Date(d.date);
                                        return date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
                                    }),
                                    datasets: [
                                        {
                                            label: 'Jobs Processed',
                                            data: dashboardStats.chart_data.map(d => d.count),
                                            borderColor: 'rgb(79, 70, 229)',
                                            backgroundColor: 'rgba(79, 70, 229, 0.1)',
                                            tension: 0.3,
                                            fill: true,
                                        }
                                    ]
                                }}
                                options={{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {
                                        legend: { display: false },
                                        tooltip: {
                                            mode: 'index',
                                            intersect: false,
                                        }
                                    },
                                    scales: {
                                        y: {
                                            beginAtZero: true,
                                            grid: { color: '#f3f4f6' },
                                            ticks: { precision: 0 }
                                        },
                                        x: {
                                            grid: { display: false }
                                        }
                                    }
                                }}
                            />
                        ) : (
                            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                                No chart data available
                            </div>
                        )}
                     </div>
                </div>
    
                {/* Storage Widget */}
                 <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative overflow-hidden group">
                    <div className="flex items-center gap-3 mb-4">
                         <CircleStackIcon className="w-6 h-6 text-indigo-600" />
                         <h3 className="font-semibold text-gray-900">System Storage</h3>
                    </div>
                    
                    <div className="space-y-4 relative z-10">
                        <div>
                            <div className="flex justify-between text-sm mb-1">
                                <span className="text-gray-500">Total Usage</span>
                                <span className="font-medium">{dashboardStats?.storage.total_size_gb} GB</span>
                            </div>
                             <div className="w-full bg-gray-100 rounded-full h-2">
                                 <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${Math.min((dashboardStats?.storage.total_size_gb || 0) / 100 * 100, 100)}%` }}></div>
                             </div>
                        </div>
                        
                        <div className="flex justify-between text-sm">
                            <span className="text-gray-500">Total Files</span>
                            <span className="font-medium">{dashboardStats?.storage.file_count}</span>
                        </div>
    
                        <button
                            onClick={handleCleanup}
                            disabled={cleaningUp}
                            className="w-full mt-2 py-2 px-3 border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                        >
                             {cleaningUp ? <ArrowPathIcon className="w-4 h-4 animate-spin"/> : <TrashIcon className="w-4 h-4"/>}
                             Cleanup Oldest 10 Jobs
                        </button>
                    </div>
                    {/* Decoration */}
                    <CircleStackIcon className="absolute -top-6 -right-6 w-32 h-32 text-gray-50 opacity-5" />
                </div>
    
                {/* Clients Table (Top 5) */}
                <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
                         <div className="flex items-center gap-2">
                            <UserGroupIcon className="w-5 h-5 text-gray-400" />
                            <h3 className="font-semibold text-gray-900">Top Clients (All Time)</h3>
                         </div>
                         <span className="text-xs text-gray-500">Sorted by Job Volume</span>
                    </div>
                    
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-100">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total Jobs</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Completed</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Failed</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reliability</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-100">
                                {dashboardStats?.clients.slice(0, 5).map((client, i) => {
                                    const reliability = client.total > 0 ? Math.round((client.completed / client.total) * 100) : 0;
                                    return (
                                        <tr key={client.name} className="hover:bg-gray-50">
                                            <td className="px-6 py-3 text-sm font-medium text-gray-900">{client.name}</td>
                                            <td className="px-6 py-3 text-sm text-gray-500">{client.total}</td>
                                            <td className="px-6 py-3 text-sm text-green-600">{client.completed}</td>
                                            <td className="px-6 py-3 text-sm text-red-600">{client.failed}</td>
                                            <td className="px-6 py-3 whitespace-nowrap">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-16 bg-gray-100 rounded-full h-1.5">
                                                        <div className={`h-1.5 rounded-full ${reliability > 90 ? 'bg-green-500' : reliability > 70 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{width: `${reliability}%`}}></div>
                                                    </div>
                                                    <span className="text-xs text-gray-500">{reliability}%</span>
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                })}
                                {!dashboardStats?.clients.length && (
                                    <tr>
                                        <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">No client data available</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                {/* System Logs (Recent 10) */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col h-[400px]">
                    <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50 shrink-0">
                         <div className="flex items-center gap-2">
                            <DocumentTextIcon className="w-5 h-5 text-gray-400" />
                            <h3 className="font-semibold text-gray-900">System Logs</h3>
                         </div>
                    </div>
                    <div className="overflow-y-auto flex-1 p-4 space-y-3">
                        {dashboardStats?.recent_logs && dashboardStats.recent_logs.length > 0 ? (
                            dashboardStats.recent_logs.map(log => (
                                <div key={log.id} className={`p-3 text-sm rounded-lg border flex gap-3 ${log.is_error ? 'bg-red-50 border-red-100' : 'bg-blue-50 border-blue-100'}`}>
                                    <div className="mt-0.5 shrink-0">
                                        {log.is_error ? <XCircleIcon className="w-5 h-5 text-red-500"/> : <CheckCircleIcon className="w-5 h-5 text-blue-500"/>}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`font-semibold ${log.is_error ? 'text-red-700' : 'text-blue-700'}`}>{log.component}</span>
                                            {log.cradle_id && <span className="bg-white px-1.5 rounded border text-xs text-gray-600">{log.cradle_id}</span>}
                                            <span className="text-xs text-gray-400">{new Date(log.created_at).toLocaleTimeString()}</span>
                                        </div>
                                        <p className="text-gray-700">{log.message}</p>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                                No recent logs
                            </div>
                        )}
                    </div>
                </div>

            </div>
          </div>
        </div>
      );
  }

  // View: List (Default / Home)
  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header - Simpler for Home */}
        <div className="mb-6 flex justify-between items-center">
            <div>
                 <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                    <FilmIcon className="w-6 h-6 text-blue-600" />
                    Recent Comparisons
                 </h1>
            </div>
            <button onClick={() => fetchJobs()} className="text-sm text-blue-600 hover:underline">Refresh List</button>
        </div>

        {/* Jobs Table & Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-gray-200 bg-white">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <h2 className="text-lg font-semibold text-gray-900">Active Jobs & History</h2>
              <div className="flex items-center space-x-3">
                <FileUpload onJobCreated={() => fetchJobs()} />
              </div>
            </div>
            
            {/* Filter Bar */}
            <div className="mt-4 flex flex-wrap items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100">
               <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mr-2 ml-1">Filters:</div>
               
               <div className="flex items-center bg-white border border-gray-200 rounded-md px-2 py-1 shadow-sm">
                  <span className="text-gray-400 mr-2">Status:</span>
                  <select 
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="text-sm bg-transparent border-none focus:ring-0 text-gray-700"
                  >
                    <option value="">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                  </select>
               </div>

               <div className="flex items-center bg-white border border-gray-200 rounded-md px-2 py-1 shadow-sm">
                  <span className="text-gray-400 mr-2">Client:</span>
                  <select 
                    value={clientFilter}
                    onChange={(e) => setClientFilter(e.target.value)}
                    className="text-sm bg-transparent border-none focus:ring-0 text-gray-700"
                  >
                    <option value="">All Clients</option>
                    {dashboardStats?.clients.map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
               </div>

               <div className="flex items-center bg-white border border-gray-200 rounded-md px-2 py-1 shadow-sm">
                  <span className="text-gray-400 mr-2">Type:</span>
                  <select 
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="text-sm bg-transparent border-none focus:ring-0 text-gray-700"
                  >
                    <option value="">All Types</option>
                    <option value="full">Full Comparison</option>
                    <option value="video_only">Video Only</option>
                    <option value="audio_only">Audio Only</option>
                    <option value="automation">Automation</option>
                  </select>
               </div>

               <div className="flex items-center bg-white border border-gray-200 rounded-md px-3 py-1 shadow-sm flex-1 min-w-[150px]">
                  <input 
                    type="text" 
                    placeholder="Search Cradle ID..." 
                    value={cradleIdFilter}
                    onChange={(e) => setCradleIdFilter(e.target.value)}
                    className="text-sm border-none focus:ring-0 w-full"
                  />
               </div>

               {(statusFilter || clientFilter || typeFilter || cradleIdFilter) && (
                 <button 
                  onClick={() => {
                    setStatusFilter("");
                    setClientFilter("");
                    setTypeFilter("");
                    setCradleIdFilter("");
                  }}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium ml-2"
                 >
                   Clear All
                 </button>
               )}
            </div>
          </div>

          {!jobs.length ? (
            <div className="px-6 py-12 text-center">
              <SparklesIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No comparison jobs</h3>
              <p className="mt-1 text-sm text-gray-500">Get started by creating your first comparison job.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Job Details</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[220px]">Metrics</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {jobs.map((job: ComparisonJob) => (
                    <tr key={job.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center cursor-pointer group" onClick={() => job.status === "completed" && onSelectJob(job)}>
                          <div className="h-10 w-10 rounded-lg bg-gradient-to-r from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-xs">
                             {job.id}
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600 transition-colors">{job.job_name}</div>
                            <div className="text-xs text-gray-400">ID: {job.cradle_id}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                         <div className="flex items-center space-x-2">
                          {getStatusIcon(job.status)}
                          <span className={getStatusBadge(job.status)}>
                            {(job.status === "pending" || job.status === "processing") ? "Processing" : job.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {job.status === "completed" && job.metrics ? (
                          <div className="flex flex-wrap gap-2">
                            <MetricBadge label="O" value={job.metrics.overall_similarity} />
                            <MetricBadge label="V" value={job.metrics.video_similarity} />
                            <MetricBadge label="A" value={job.metrics.audio_similarity} />
                          </div>
                        ) : (
                          <span className="text-gray-300 text-xs">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(job.created_at)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {(job.status === "processing" || job.status === "pending") ? (
                           <div className="w-full max-w-[140px]">
                             <div className="flex justify-between text-xs mb-1">
                               <span className="text-blue-600 font-medium">{Math.round(job.progress || 0)}%</span>
                               {job.started_at && <JobTimer startedAt={job.started_at} />}
                             </div>
                             <div className="w-full bg-gray-200 rounded-full h-1.5">
                               <div className="bg-blue-600 h-1.5 rounded-full transition-all duration-500" style={{ width: `${job.progress || 0}%` }}></div>
                             </div>
                           </div>
                        ) : formatDuration(job.processing_duration)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex items-center justify-end space-x-2">
                            {job.status === "completed" && (
                                <button onClick={() => onSelectJob(job)} className="p-1.5 text-green-600 hover:bg-green-50 rounded"><EyeIcon className="w-5 h-5"/></button>
                            )}
                             {job.status === "pending" && (
                                <button onClick={() => handleStartJob(job.id)} className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"><PlayIcon className="w-5 h-5"/></button>
                            )}
                             {job.status === "processing" && (
                                <button onClick={() => handleStopJob(job.id)} className="p-1.5 text-amber-600 hover:bg-amber-50 rounded"><PauseIcon className="w-5 h-5"/></button>
                            )}
                             {(job.status === "failed" || job.status === "cancelled") && (
                                <button onClick={() => handleRetryJob(job.id)} className="p-1.5 text-blue-600 hover:bg-blue-50 rounded"><ArrowPathIcon className="w-5 h-5"/></button>
                            )}
                             <button onClick={() => handleDeleteJob(job.id)} className="p-1.5 text-red-600 hover:bg-red-50 rounded"><TrashIcon className="w-5 h-5"/></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
