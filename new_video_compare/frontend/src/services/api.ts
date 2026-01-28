// frontend/src/services/api.ts
import { ComparisonJob, FileUpload } from "../types"; // ✅ FileInfo → FileUpload

const API_BASE_URL = "http://localhost:8001/api/v1";

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

class CompareAPI {
  async getJobs(): Promise<ComparisonJob[]> {
    const response = await fetch(`${API_BASE_URL}/compare/`);
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
    return `${API_BASE_URL}/files/files/stream/${fileId}`;
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
      throw new Error("Failed to cancel job");
    }
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
    const response = await fetch(
      `${API_BASE_URL}/compare/auto-pair/${cradleId}`,
      {
        method: "POST",
      }
    );
    if (!response.ok) {
      throw new Error("Failed to create auto-pair job");
    }
    return response.json();
  }

  async uploadFile(file: File, fileType: string = "acceptance"): Promise<FileUpload> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);

    const response = await fetch(`${API_BASE_URL}/files/files/upload`, {
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
