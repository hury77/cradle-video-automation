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
}

const Dashboard: React.FC<DashboardProps> = ({ onSelectJob }) => {
  const [jobs, setJobs] = useState<ComparisonJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async () => {
    try {
      // Don't set loading on background refresh
      if (!jobs.length) setLoading(true);

      const [jobsResponse, statsResponse] = await Promise.all([
        compareApi.getJobs(),
        compareApi.getDashboardStats().catch(err => null)
      ]);
      
      setJobs(jobsResponse);
      if (statsResponse) setDashboardStats(statsResponse);
      
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
    } finally {
      if (loading) setLoading(false);
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
    if (!window.confirm("Delete 10 oldest jobs + associated files?")) return;
    setCleaningUp(true);
    try {
      const result = await compareApi.cleanupOldJobs(10);
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

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="mb-8 flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg shadow-sm">
                 <FilmIcon className="w-6 h-6 text-white" />
              </div>
              Automation Dashboard
            </h1>
            <p className="text-gray-500 mt-1 ml-14">Live monitoring of Video QA automation</p>
          </div>
          <button onClick={fetchJobs} className="text-sm text-blue-600 hover:underline">Refresh Data</button>
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
                                }).reverse(),
                                datasets: [
                                    {
                                        label: 'Jobs Processed',
                                        data: dashboardStats.chart_data.map(d => d.count).reverse(),
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
        </div>

        {/* Jobs Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
            <div className="flex items-center space-x-3">
              <FileUpload onJobCreated={fetchJobs} />
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
              {/* Existing Table Structure but slight styled to match new design */}
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Job Details</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
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
                           {/* Action Buttons reusing logic */}
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
