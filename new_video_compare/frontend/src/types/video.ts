export interface VideoPlayerState {
  currentTime: number;
  duration: number;
  playing: boolean;
  volume: number;
  muted: boolean;
}

export interface SyncedPlayback {
  masterPlayer: 'acceptance' | 'emission';
  syncEnabled: boolean;
  timeOffset: number;
}

export interface DifferenceMarker {
  id: string;
  timestamp: number;
  confidence: number;
  type: 'video' | 'audio';
  description: string;
  severity: 'low' | 'medium' | 'high';
}
