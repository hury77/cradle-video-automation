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
  CircleStackIcon, // NEW
} from "@heroicons/react/24/outline";

import { ComparisonJob } from "../types";
import { compareApi, StorageStats } from "../services/api";
import FileUpload from "./FileUpload";

const JobTimer: React.FC<{ startedAt?: string }> = ({ startedAt }) => {
  const [elapsed, setElapsed] = useState<number>(0);

  useEffect(() => {
    if (!startedAt) return;
    
    // Backend returns UTC, but might miss 'Z'. Ensure we treat it as UTC.
    const dateStr = startedAt.endsWith('Z') || startedAt.includes('+') ? startedAt : `${startedAt}Z`;
    const start = new Date(dateStr).getTime();
    
    // Prevent negative elapsed times if clocks are slightly off
    setElapsed(Math.max(0, Date.now() - start));

    const interval = setInterval(() => {
      setElapsed(Math.max(0, Date.now() - start));
    }, 1000);

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

interface JobStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
}

const Dashboard: React.FC<DashboardProps> = ({ onSelectJob }) => {
  const [jobs, setJobs] = useState<ComparisonJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<JobStats>({
    total: 0,
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0,
  });
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      setLoading(true);

      const [jobsResponse, statsResponse] = await Promise.all([
        compareApi.getJobs(),
        compareApi.getDashboardStats().catch(err => null)
      ]);
      
      setJobs(jobsResponse);
      if (statsResponse) setStorageStats(statsResponse);
      
      const response = jobsResponse; // keeping existing logic variable name

      // ✅ UPROSZONY KOD - bez reduce, z forEach
      const newStats: JobStats = {
        total: response.length,
        pending: 0,
        processing: 0,
        completed: 0,
        failed: 0,
      };

      response.forEach((job: ComparisonJob) => {
        switch (job.status) {
          case "pending":
            newStats.pending++;
            break;
          case "processing":
            newStats.processing++;
            break;
          case "completed":
            newStats.completed++;
            break;
          case "failed":
            newStats.failed++;
            break;
          default:
            break;
        }
      });

      setStats(newStats);
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
    } finally {
      setLoading(false);
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
    if (!window.confirm("Are you sure you want to delete the 10 oldest jobs and their associated files? This cannot be undone.")) return;
    
    setCleaningUp(true);
    try {
      const result = await compareApi.cleanupOldJobs(10);
      alert(`Cleanup complete!\n${result.message}\nFreed: ${result.freed_space_mb} MB`);
      fetchJobs();
    } catch (error) {
      console.error("Cleanup failed:", error);
      alert("Cleanup failed.");
    } finally {
      setCleaningUp(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
      case "processing":
        return <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin" />;
      case "completed":
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case "failed":
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      default:
        return <ClockIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses =
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";

    switch (status) {
      case "pending":
      case "processing":
        return `${baseClasses} bg-blue-100 text-blue-800`;
      case "completed":
        return `${baseClasses} bg-green-100 text-green-800`;
      case "failed":
        return `${baseClasses} bg-red-100 text-red-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return "-";
    return `${seconds.toFixed(2)}s`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
        <div className="max-w-[1600px] mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-64 mb-4"></div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white rounded-lg p-6 shadow-sm">
                  <div className="h-4 bg-gray-200 rounded w-16 mb-2"></div>
                  <div className="h-8 bg-gray-200 rounded w-8"></div>
                </div>
              ))}
            </div>
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-200 rounded"></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <div className="p-2 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg">
              <FilmIcon className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
              Video Comparison Dashboard
            </h1>
          </div>
          <p className="text-gray-600">
            Manage and monitor video comparison jobs
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          {/* Storage Card (NEW) */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow relative overflow-hidden group">
            <div className={`absolute top-0 right-0 p-4 transition-transform ${cleaningUp ? 'animate-pulse' : ''}`}>
              <CircleStackIcon className="w-16 h-16 text-gray-100 -mr-4 -mt-4 transform rotate-12 group-hover:rotate-0 transition-transform" />
            </div>
            
            <div className="relative z-10">
              <p className="text-sm font-medium text-gray-600 mb-1">Storage Usage</p>
              <p className="text-2xl font-bold text-gray-900">
                {storageStats ? `${storageStats.storage.total_size_gb} GB` : '...'}
              </p>
              <p className="text-xs text-gray-500 mt-1 mb-3">
                {storageStats ? `${storageStats.storage.file_count} files` : 'Calculating...'}
              </p>
              
              <button
                onClick={handleCleanup}
                disabled={cleaningUp}
                className="w-full py-1.5 px-3 bg-white border border-gray-200 hover:bg-red-50 hover:border-red-200 text-gray-600 hover:text-red-600 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1"
                title="Delete 10 oldest jobs"
              >
                {cleaningUp ? (
                  <ArrowPathIcon className="w-3 h-3 animate-spin" />
                ) : (
                  <TrashIcon className="w-3 h-3" />
                )}
                {cleaningUp ? "Cleaning..." : "Delete 10 Oldest"}
              </button>
            </div>
             {/* Progress bar background hint */}
             <div className="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-blue-500 to-purple-500 opacity-20 w-full"></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Jobs</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total}
                </p>
              </div>
              <div className="p-3 bg-gray-100 rounded-lg">
                <DocumentTextIcon className="w-6 h-6 text-gray-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Processing</p>
                <p className="text-2xl font-bold text-blue-600">
                  {stats.processing}
                </p>
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <ArrowPathIcon className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Completed</p>
                <p className="text-2xl font-bold text-green-600">
                  {stats.completed}
                </p>
              </div>
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircleIcon className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Failed</p>
                <p className="text-2xl font-bold text-red-600">
                  {stats.failed}
                </p>
              </div>
              <div className="p-3 bg-red-100 rounded-lg">
                <XCircleIcon className="w-6 h-6 text-red-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Jobs Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Comparison Jobs
              </h2>
              <div className="flex items-center space-x-3">
                <FileUpload onJobCreated={fetchJobs} />
                <button
                  onClick={fetchJobs}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                >
                  <ArrowPathIcon className="w-4 h-4 mr-2" />
                  Refresh
                </button>
              </div>
            </div>
          </div>

          {jobs.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <SparklesIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No comparison jobs
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Get started by creating your first comparison job.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Job Details
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Files
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Duration
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {jobs.map((job: ComparisonJob) => (
                    <tr
                      key={job.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div 
                          className="flex items-center cursor-pointer group"
                          onClick={() => job.status === "completed" && onSelectJob(job)}
                        >
                          <div className="flex-shrink-0 h-10 w-10">
                            <div className="h-10 w-10 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center group-hover:scale-105 transition-transform duration-200">
                              <FilmIcon className="w-5 h-5 text-white" />
                            </div>
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
                              {job.job_name}
                            </div>
                            <div className="text-sm text-gray-500">
                              Cradle ID: {job.cradle_id}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center space-x-2">
                          {getStatusIcon(job.status)}
                          <span className={getStatusBadge(job.status)}>
                            {(job.status === "pending" || job.status === "processing") 
                              ? "Processing" 
                              : job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div className="flex items-center space-x-4">
                          <div className="flex items-center space-x-1">
                            <DocumentTextIcon className="w-4 h-4" />
                            <span>Accept: {job.acceptance_file_id}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <DocumentTextIcon className="w-4 h-4" />
                            <span>Emission: {job.emission_file_id}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(job.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {job.status === "processing" || job.status === "pending" ? (
                           <div className="w-full max-w-[140px]">
                             <div className="flex justify-between text-xs mb-1">
                               <span className="text-blue-600 font-medium">{Math.round(job.progress || 0)}%</span>
                               {job.started_at && <JobTimer startedAt={job.started_at} />}
                             </div>
                             <div className="w-full bg-gray-200 rounded-full h-2">
                               <div 
                                 className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                                 style={{ width: `${job.progress || 0}%` }}
                               ></div>
                             </div>
                           </div>
                        ) : (
                           formatDuration(job.processing_duration)
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex items-center justify-end space-x-2">
                          {job.status === "completed" && (
                            <button
                              onClick={() => onSelectJob(job)}
                              className="inline-flex items-center p-2 border border-transparent rounded-lg text-green-600 hover:bg-green-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors"
                              title="View Results"
                            >
                              <EyeIcon className="w-4 h-4" />
                            </button>
                          )}

                          {job.status === "pending" && (
                            <button
                              onClick={() => handleStartJob(job.id)}
                              className="inline-flex items-center p-2 border border-transparent rounded-lg text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                              title="Start Job"
                            >
                              <PlayIcon className="w-4 h-4" />
                            </button>
                          )}

                          {job.status === "processing" && (
                            <button
                              onClick={() => handleStopJob(job.id)}
                              className="inline-flex items-center p-2 border border-transparent rounded-lg text-yellow-600 hover:bg-yellow-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 transition-colors"
                              title="Stop Job"
                            >
                              <PauseIcon className="w-4 h-4" />
                            </button>
                          )}

                          {(job.status === "failed" || job.status === "cancelled") && (
                            <button
                              onClick={() => handleRetryJob(job.id)}
                              className="inline-flex items-center p-2 border border-transparent rounded-lg text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                              title="Retry Job"
                            >
                              <ArrowPathIcon className="w-4 h-4" />
                            </button>
                          )}

                          <button
                            onClick={() => handleDeleteJob(job.id)}
                            className="inline-flex items-center p-2 border border-transparent rounded-lg text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors"
                            title="Delete Job"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
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
