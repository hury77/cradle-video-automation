// frontend/src/services/api.ts
import { ComparisonJob, FileUpload } from "../types"; // ✅ FileInfo → FileUpload

const API_BASE_URL = "/api/v1";

// Types for comparison results
export interface ComparisonResults {
  job_id: number;
  job_name: string;
  status: string;
  completed_at: string | null;
  acceptance_file: {
    id: number;
    filename: string;
    duration: number | null;
    width: number | null;
    height: number | null;
    fps: number | null;
  };
  emission_file: {
    id: number;
    filename: string;
    duration: number | null;
    width: number | null;
    height: number | null;
    fps: number | null;
  };
  overall_result: {
    overall_similarity: number | null;
    is_match: boolean | null;
    video_similarity: number | null;
    audio_similarity: number | null;
    video_differences_count: number | null;
    audio_differences_count: number | null;
    report_data?: {
      ocr?: {
        timeline?: Array<{
          timestamp: number;
          text: string;
          source: string;
          confidence: number;
          is_difference: boolean;
        }>;
        only_in_acceptance?: string[];
        only_in_emission?: string[];
      };
    };
  } | null;
  video_result: {
    similarity_score: number | null;
    total_frames: number | null;
    different_frames: number | null;
    ssim_score: number | null;
    histogram_similarity: number | null;
    algorithm_used: string | null;
  } | null;
  audio_result: {
    similarity_score: number | null;
    spectral_similarity: number | null;
    mfcc_similarity: number | null;
    cross_correlation: number | null;
    sync_offset_ms: number | null;
  } | null;
  differences: Array<{
    timestamp_seconds: number;
    duration_seconds: number;
    difference_type: string;
    severity: string;
    confidence: number;
    description: string | null;
  }>;

}

export interface KPIStats {
  total_jobs: number;
  active_jobs: number;
  success_rate: number;
  avg_processing_time: number;
  throughput_24h: number;
}

export interface ClientStats {
  name: string;
  total: number;
  completed: number;
  failed: number;
}

export interface DashboardStats {
  kpi: KPIStats;
  chart_data: Array<{ date: string; count: number }>;
  breakdown: {
    completed: number;
    failed: number;
    pending: number;
  };
  clients: ClientStats[];
  storage: {
    total_size_gb: number;
    file_count: number;
    db_size_mb: number;
    kb_count: number;
  };
  recent_logs?: Array<{
    id: number;
    cradle_id: string | null;
    component: string;
    action: string;
    message: string;
    is_error: boolean;
    created_at: string;
  }>;
}

export interface CleanupResult {
  message: string;
  deleted_jobs: number;
  freed_space_mb: number;
}

export interface AutomationLog {
  id: number;
  cradle_id: string | null;
  component: string;
  action: string;
  message: string;
  is_error: boolean;
  details: Record<string, any> | null;
  created_at: string;
}

export interface AutomationLogsResponse {
  total: number;
  results: AutomationLog[];
  components: string[];
}

class CompareAPI {
  async getJobs(filters?: {
    status?: string;
    cradleId?: string;
    clientName?: string;
    comparisonType?: string;
    skip?: number;
    limit?: number;
  }): Promise<ComparisonJob[]> {
    let url = `${API_BASE_URL}/compare/?`;
    if (filters) {
      if (filters.status) url += `status=${encodeURIComponent(filters.status)}&`;
      if (filters.cradleId) url += `cradle_id=${encodeURIComponent(filters.cradleId)}&`;
      if (filters.clientName) url += `client_name=${encodeURIComponent(filters.clientName)}&`;
      if (filters.comparisonType) url += `comparison_type=${encodeURIComponent(filters.comparisonType)}&`;
      if (filters.skip !== undefined) url += `skip=${filters.skip}&`;
      if (filters.limit !== undefined) url += `limit=${filters.limit}&`;
    }
    
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("Failed to fetch jobs");
    }
    return response.json();
  }

  async getJob(jobId: number): Promise<ComparisonJob> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}`);
    if (!response.ok) {
      throw new Error("Failed to fetch job");
    }
    return response.json();
  }

  async getJobResults(jobId: number): Promise<ComparisonResults> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}/results`);
    if (!response.ok) {
      throw new Error("Failed to fetch job results");
    }
    return response.json();
  }

  getVideoStreamUrl(fileId: number): string {
    return `${API_BASE_URL}/files/stream/${fileId}`;
  }

  async startJob(jobId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}/start`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Failed to start job");
    }
  }

  async cancelJob(jobId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}/cancel`, {
      method: "POST",
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => null); // Try to get error details
      throw new Error(errorData?.detail || "Failed to cancel job");
    }
  }

  async retryJob(jobId: number): Promise<ComparisonJob> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}/retry`, {
      method: "POST",
    });
    if (!response.ok) {
       const errorData = await response.json().catch(() => null);
       throw new Error(errorData?.detail || "Failed to retry job");
    }
    return response.json();
  }

  async deleteJob(jobId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/compare/${jobId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Failed to delete job");
    }
  }

  async autoPairJob(cradleId: string): Promise<ComparisonJob> {
    const response = await fetch(`${API_BASE_URL}/compare/auto-pair/${cradleId}`, {
      method: "POST",
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.detail || "Failed to auto-pair job");
    }
    
    return response.json();
  }

  async getDashboardStats(): Promise<DashboardStats> {
    const response = await fetch(`${API_BASE_URL}/dashboard/stats`);
    if (!response.ok) {
        throw new Error("Failed to fetch dashboard stats");
    }
    return response.json();
  }

  async cleanupOldJobs(days: number = 14, count: number = 50): Promise<CleanupResult> {
    const response = await fetch(`${API_BASE_URL}/dashboard/cleanup?days=${days}&count=${count}`, {
        method: "DELETE"
    });
    if (!response.ok) {
        throw new Error("Failed to cleanup jobs");
    }
    return response.json();
  }

  async getAutomationLogs(
    skip: number = 0,
    limit: number = 50,
    component?: string,
    onlyErrors: boolean = false,
    cradleId?: string
  ): Promise<AutomationLogsResponse> {
    let url = `${API_BASE_URL}/dashboard/automation-logs?skip=${skip}&limit=${limit}`;
    if (component) url += `&component=${encodeURIComponent(component)}`;
    if (onlyErrors) url += `&only_errors=true`;
    if (cradleId) url += `&cradle_id=${encodeURIComponent(cradleId)}`;

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("Failed to fetch automation logs");
    }
    return response.json();
  }

  async uploadFile(file: File, fileType: string = "acceptance"): Promise<FileUpload> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);

    const response = await fetch(`${API_BASE_URL}/files/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to upload file");
    }
    return response.json();
  }

  async createJob(
    jobName: string,
    acceptanceFileId: number,
    emissionFileId: number,
    comparisonType: string = "full"
  ): Promise<ComparisonJob> {
    const response = await fetch(`${API_BASE_URL}/compare/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        job_name: jobName,
        acceptance_file_id: acceptanceFileId,
        emission_file_id: emissionFileId,
        comparison_type: comparisonType,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to create job");
    }
    return response.json();
  }
}

export const compareApi = new CompareAPI();
