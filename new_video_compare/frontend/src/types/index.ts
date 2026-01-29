// frontend/src/types/index.ts
export interface FileInfo {
  id: number;
  filename: string;
  original_name?: string;
  file_type: string;
  duration?: number | null;
  width?: number | null;
  height?: number | null;
}

export interface ComparisonJob {
  id: number;
  job_name: string;
  cradle_id: string;
  acceptance_file_id: number;
  emission_file_id: number;
  acceptance_file?: FileInfo;
  emission_file?: FileInfo;
  sensitivity_level?: "low" | "medium" | "high";
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  created_at: string;
  updated_at: string;
  processing_duration?: number; // seconds
  started_at?: string;
  completed_at?: string;
  results?: any;
}

export interface FileUpload {
  id: number;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  created_at: string;
}

export interface WebSocketMessage {
  action: string;
  data: any;
  timestamp: string;
}

export interface ComparisonResults {
  video_similarity: number;
  audio_similarity: number;
  overall_similarity: number;
  video_algorithms: Record<string, number>;
  audio_algorithms: Record<string, number>;
  total_frames: number;
  processed_frames: number;
  processing_time: number;
}
