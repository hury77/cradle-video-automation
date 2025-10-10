// frontend/src/types/index.ts
export interface ComparisonJob {
  id: number;
  job_name: string;
  cradle_id: string;
  acceptance_file_id: number;
  emission_file_id: number;
  status: "pending" | "processing" | "completed" | "failed";
  created_at: string;
  updated_at: string;
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
