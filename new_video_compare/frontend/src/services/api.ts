// frontend/src/services/api.ts
import { ComparisonJob, FileUpload } from "../types"; // ✅ FileInfo → FileUpload

const API_BASE_URL = "http://localhost:8001/api/v1";

class CompareAPI {
  async getJobs(): Promise<ComparisonJob[]> {
    const response = await fetch(`${API_BASE_URL}/compare/`);
    if (!response.ok) {
      throw new Error("Failed to fetch jobs");
    }
    return response.json();
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

  async uploadFile(file: File): Promise<FileUpload> {
    // ✅ FileInfo → FileUpload
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}/files/files/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to upload file");
    }
    return response.json();
  }
}

export const compareApi = new CompareAPI();
