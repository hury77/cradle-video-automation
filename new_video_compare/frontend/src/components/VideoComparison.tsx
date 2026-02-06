// frontend/src/components/VideoComparison.tsx
import React, { useState, useEffect, useRef } from "react";
import { ComparisonJob } from "../types";
import {
  PlayIcon,
  PauseIcon,
  EyeIcon,
  EyeSlashIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ChartBarSquareIcon,
  DocumentChartBarIcon,
  ForwardIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import DifferenceInspector from "./DifferenceInspector";

interface VideoComparisonProps {
  job: ComparisonJob;
  onJobReanalyzed?: () => void;
}

interface ApiResults {
  job_id: number;
  job_name: string;
  status: string;
  overall_result: {
    overall_similarity: number | null;
    is_match: boolean | null;
    video_similarity: number | null;
    audio_similarity: number | null;
    video_differences_count: number | null;
    audio_differences_count: number | null;
    report_data?: {
      video?: {
        diff_frames?: Record<string, string>;
      };
      ocr?: {
        text_similarity: number | null;
        has_differences: boolean;
        timeline?: Array<{
          timestamp: number;
          text: string;
          source: string;
          confidence: number;
          is_difference: boolean;
        }>;
        differences: Array<{
          type: string;
          text: string;
          timestamp: number;
          source: string;
          confidence: number;
        }>;
        only_in_acceptance: string[];
        only_in_emission: string[];
        common_texts: string[];
      };
      audio?: {
        loudness?: {
          acceptance?: {
            integrated_lufs: number;
            true_peak_db: number;
            duration_seconds: number;
          };
          emission?: {
            integrated_lufs: number;
            true_peak_db: number;
            duration_seconds: number;
          };
          comparison?: {
            lufs_difference: number;
            peak_difference_db: number;
            is_lufs_match: boolean;
            is_peak_match: boolean;
          };
          has_loudness_differences: boolean;
        };
        similarity?: {
          mfcc_similarity: number;
          spectral_similarity: number;
          overall_audio_similarity: number;
        };
        source_separation?: {
          acceptance?: {
            vocals_proportion: number;
            music_proportion: number;
            has_vocals: boolean;
          };
          emission?: {
            vocals_proportion: number;
            music_proportion: number;
            has_vocals: boolean;
          };
        };
        voiceover?: {
          voice_similarity: number;
          is_same_voice: boolean;
          timing?: {
            average_offset_seconds: number;
            is_synced: boolean;
          };
        };
        speech_to_text?: {
          text_similarity: number;
          is_text_match: boolean;
          acceptance_text: string;
          emission_text: string;
          comparison?: {
            word_differences: Array<{
              type: string;
              acceptance: string;
              emission: string;
            }>;
            total_differences: number;
          };
        };
        has_loudness_differences: boolean;
      };
    };
  } | null;
  video_result: {
    similarity_score: number | null;
    total_frames: number | null;
    different_frames: number | null;
    ssim_score: number | null;
    histogram_similarity: number | null;
  } | null;
  audio_result: {
    similarity_score: number | null;
    spectral_similarity: number | null;
    mfcc_similarity: number | null;
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

const VideoComparison: React.FC<VideoComparisonProps> = ({ job, onJobReanalyzed }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [acceptanceVolume, setAcceptanceVolume] = useState(1);
  const [emissionVolume, setEmissionVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // Sync heatmap with playback
  const [currentDiffImage, setCurrentDiffImage] = useState<string | null>(null);

  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<ApiResults | null>(null);
  // Inspector Modal State
  const [reanalyzing, setReanalyzing] = useState(false);
  const [showInspector, setShowInspector] = useState(false);
  const [inspectorInitialTimestamp, setInspectorInitialTimestamp] = useState<number | null>(null);

  
  // Video loading states
  const [acceptanceLoading, setAcceptanceLoading] = useState(true);
  const [emissionLoading, setEmissionLoading] = useState(true);
  const [acceptanceError, setAcceptanceError] = useState(false);
  const [emissionError, setEmissionError] = useState(false);

  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);

  // Build video URLs from job data (note: double /files/ in path matches API router)
  const acceptanceVideoUrl = `http://localhost:8001/api/v1/files/files/stream/${job.acceptance_file_id}`;
  const emissionVideoUrl = `http://localhost:8001/api/v1/files/files/stream/${job.emission_file_id}`;

  // Load results from API
  useEffect(() => {
    const loadResults = async () => {
      if (job.status !== "completed") {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(
          `http://localhost:8001/api/v1/compare/${job.id}/results`
        );
        if (response.ok) {
          const data = await response.json();
          setResults(data);
        }
      } catch (err) {
        console.warn("Error loading results:", err);
      } finally {
        setLoading(false);
      }
    };

    loadResults();
  }, [job.id, job.status]);

  // Sync heatmap with playback
  useEffect(() => {
    if (!showHeatmap || !results?.overall_result?.report_data?.video?.diff_frames) {
      setCurrentDiffImage(null);
      return;
    }

    const diffFrames = results.overall_result.report_data.video.diff_frames;
    // Find closest frame (timeline is float seconds)
    // We check if current time is close to any diff timestamp (within 0.5s)
    const time = Math.floor(currentTime); // 1fps, so integer part is enough usually
    
    // Check key directly first
    let foundImage = diffFrames[time.toString()] || diffFrames[time.toFixed(1)];
    
    if (!foundImage) {
        // Fallback: search keys
        const keys = Object.keys(diffFrames).map(Number);
        const closest = keys.reduce((prev, curr) => 
            Math.abs(curr - currentTime) < Math.abs(prev - currentTime) ? curr : prev
        , keys[0]);
        
        if (Math.abs(closest - currentTime) < 0.6) {
           foundImage = diffFrames[closest.toString()];
        }
    }
    
    setCurrentDiffImage(foundImage || null);
  }, [currentTime, showHeatmap, results]);

  // Get values from API results with fallbacks
  const overallScore = results?.overall_result?.overall_similarity ?? 0;
  const videoSimilarity = results?.video_result?.similarity_score ?? 0;
  const audioSimilarity = results?.audio_result?.similarity_score ?? 0;
  const videoDifferences = results?.video_result?.different_frames ?? 0;
  const totalFrames = results?.video_result?.total_frames ?? 0;
  const differences = results?.differences ?? [];
  const differencesFound = differences.length > 0 || videoDifferences > 0;

  // Setup video event listeners
  useEffect(() => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];

    const handleLoadedMetadata = () => {
      if (acceptanceVideoRef.current) {
        setDuration(acceptanceVideoRef.current.duration);
      }
    };

    const handleTimeUpdate = () => {
      if (acceptanceVideoRef.current) {
        setCurrentTime(acceptanceVideoRef.current.currentTime);
      }
    };

    videos.forEach((video) => {
      if (video) {
        video.addEventListener("loadedmetadata", handleLoadedMetadata);
        video.addEventListener("timeupdate", handleTimeUpdate);
      }
    });

    return () => {
      videos.forEach((video) => {
        if (video) {
          video.removeEventListener("loadedmetadata", handleLoadedMetadata);
          video.removeEventListener("timeupdate", handleTimeUpdate);
        }
      });
    };
  }, []);

  // Synchronized play/pause
  const togglePlayPause = () => {
    console.log("Toggle Play/Pause clicked! Is Playing:", isPlaying);
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];

    if (isPlaying) {
      videos.forEach((video) => video?.pause());
    } else {
      const syncTime = acceptanceVideoRef.current?.currentTime ?? 0;
      videos.forEach((video) => {
        if (video) {
          video.currentTime = syncTime;
          video.play();
        }
      });
    }

    setIsPlaying(!isPlaying);
  };

  const handleSeek = (time: number) => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => {
      if (video) {
        video.currentTime = time;
      }
    });
    setCurrentTime(time);
  };

  const jumpToDifference = (timestamp: number) => {
    handleSeek(timestamp);
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => video?.pause());
    setIsPlaying(false);
  };

  // Sync volume
  useEffect(() => {
    if (acceptanceVideoRef.current) {
      acceptanceVideoRef.current.volume = isMuted ? 0 : acceptanceVolume;
    }
  }, [acceptanceVolume, isMuted]);

  useEffect(() => {
    if (emissionVideoRef.current) {
      emissionVideoRef.current.volume = isMuted ? 0 : emissionVolume;
    }
  }, [emissionVolume, isMuted]);

  const handleAcceptanceVolumeChange = (newVolume: number) => {
    setAcceptanceVolume(newVolume);
    if (isMuted && newVolume > 0) setIsMuted(false); // Unmute if volume is increased
  };

  const handleEmissionVolumeChange = (newVolume: number) => {
    setEmissionVolume(newVolume);
    if (isMuted && newVolume > 0) setIsMuted(false); // Unmute if volume is increased
  };

  const toggleMute = () => {
    const newMuted = !isMuted;
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => {
      if (video) {
        video.muted = newMuted;
      }
    });
    setIsMuted(newMuted);
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  const getOverallStatus = (similarity: number) => {
    if (similarity >= 0.95)
      return { label: "Excellent Match", color: "text-green-600", bg: "bg-green-100" };
    if (similarity >= 0.9)
      return { label: "Good Match", color: "text-blue-600", bg: "bg-blue-100" };
    if (similarity >= 0.8)
      return { label: "Fair Match", color: "text-yellow-600", bg: "bg-yellow-100" };
    if (similarity > 0)
      return { label: "Poor Match", color: "text-red-600", bg: "bg-red-100" };
    return { label: "Processing...", color: "text-gray-600", bg: "bg-gray-100" };
  };

  const status = getOverallStatus(overallScore);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {job.job_name}
              </h1>
              <p className="text-gray-600">Cradle ID: {job.cradle_id || "N/A"}</p>
              {differencesFound && (
                <p className="text-sm text-orange-600 mt-1">
                  ⚠️ Differences detected ({videoDifferences} video frames, {differences.length} timestamps)
                </p>
              )}
            </div>

            <div className="flex items-center space-x-4">
              <div
                className={`inline-flex items-center px-4 py-2 rounded-full text-sm font-medium ${status.bg} ${status.color}`}
              >
                <div className="w-2 h-2 bg-current rounded-full mr-2"></div>
                {status.label}
              </div>

              <button
                onClick={() => setShowResults(!showResults)}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              >
                <ChartBarSquareIcon className="w-4 h-4 mr-2" />
                {showResults ? "Hide Results" : "Show Results"}
              </button>
              
               {/* Inspect Button */}
               {differencesFound && (
                <button
                    onClick={() => {
                        setShowInspector(true);
                        setIsPlaying(false); // Pause main players
                    }}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
                >
                    <EyeIcon className="w-4 h-4 mr-2" />
                    Inspect Differences
                </button>
               )}
            </div>
          </div>
        </div>

        {/* Difference Inspector Modal */}
        <DifferenceInspector 
            isOpen={showInspector}
            onClose={() => setShowInspector(false)}
            differences={differences || []}
            diffFrames={results?.overall_result?.report_data?.video?.diff_frames || {}}
            videoUrls={{
                acceptance: acceptanceVideoUrl,
                emission: emissionVideoUrl
            }}
            metadata={{
                acceptanceName: job.acceptance_file?.original_name || job.acceptance_file?.filename || 'Acceptance',
                emissionName: job.emission_file?.original_name || job.emission_file?.filename || 'Emission',
                acceptanceDims: { width: job.acceptance_file?.width || 0, height: job.acceptance_file?.height || 0 },
                emissionDims: { width: job.emission_file?.width || 0, height: job.emission_file?.height || 0 },
            }}
            initialTimestamp={inspectorInitialTimestamp}
        />

        {/* Video Players - Side by Side */}
        <div id="video-player-section" className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Acceptance Video */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-green-50">
              <div className="flex flex-col">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-green-800">
                    Acceptance Video
                  </h3>
                  <span className="text-xs text-gray-500">
                    ID: {job.acceptance_file_id}
                  </span>
                </div>
                <div className="flex items-center mt-1 space-x-2">
                  <p className="text-xs text-gray-600 truncate min-w-0" title={job.acceptance_file?.original_name || job.acceptance_file?.filename || ''}>
                    {job.acceptance_file?.original_name || job.acceptance_file?.filename || 'Loading...'}
                  </p>
                  {job.acceptance_file?.width && job.acceptance_file?.height && (
                    <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                      {job.acceptance_file.width}x{job.acceptance_file.height}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="p-4">
              <div className="aspect-video bg-black rounded-lg overflow-hidden relative">
                {acceptanceLoading && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 z-10">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-green-500 border-t-transparent mb-4"></div>
                    <p className="text-white text-sm">Loading video...</p>
                    <p className="text-gray-400 text-xs mt-1">Transcoding if needed</p>
                  </div>
                )}
                {acceptanceError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 z-10">
                    <p className="text-red-400 text-sm">Failed to load video</p>
                    <button 
                      onClick={() => {
                        setAcceptanceError(false);
                        setAcceptanceLoading(true);
                        if (acceptanceVideoRef.current) {
                          acceptanceVideoRef.current.load();
                        }
                      }}
                      className="mt-2 px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700"
                    >
                      Retry
                    </button>
                  </div>
                )}
                <video
                  ref={acceptanceVideoRef}
                  className="w-full h-full object-contain"
                  src={acceptanceVideoUrl}
                  preload="auto"
                  onLoadedData={() => setAcceptanceLoading(false)}
                  onCanPlay={() => setAcceptanceLoading(false)}
                  onError={() => {
                    setAcceptanceLoading(false);
                    setAcceptanceError(true);
                  }}
                />
              </div>
            </div>
            {/* Acceptance Volume Control */}
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 flex items-center space-x-2">
              <SpeakerWaveIcon className="w-4 h-4 text-gray-500" />
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : acceptanceVolume}
                onChange={(e) => handleAcceptanceVolumeChange(Number(e.target.value))}
                className="w-24 h-1.5 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-green-600"
              />
              <span className="text-xs text-gray-500 w-8 tabular-nums font-medium">
                {Math.round((isMuted ? 0 : acceptanceVolume) * 100)}%
              </span>
            </div>
          </div>

          {/* Emission Video */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-red-50">
              <div className="flex flex-col">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-red-800">
                    Emission Video
                  </h3>
                  <span className="text-xs text-gray-500">
                    ID: {job.emission_file_id}
                  </span>
                </div>
                <div className="flex items-center space-x-2 mt-1">
                    <div className="flex items-center space-x-2 flex-grow min-w-0">
                      <p className="text-xs text-gray-600 truncate" title={job.emission_file?.original_name || job.emission_file?.filename || ''}>
                      {job.emission_file?.original_name || job.emission_file?.filename || 'Loading...'}
                      </p>
                      {job.emission_file?.width && job.emission_file?.height && (
                          <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          {job.emission_file.width}x{job.emission_file.height}
                          </span>
                      )}
                    </div>
                    
                    {/* Heatmap Toggle */}
                    {results?.overall_result?.report_data?.video?.diff_frames && (
                        <button
                            onClick={() => setShowHeatmap(!showHeatmap)}
                            className={`flex items-center space-x-1 px-2 py-0.5 rounded-lg text-xs font-medium transition-colors ${
                                showHeatmap 
                                ? 'bg-red-100 text-red-700 border border-red-200' 
                                : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
                            }`}
                            title="Toggle Visual Difference Overlay (Heatmap)"
                        >
                            {showHeatmap ? <EyeIcon className="w-3.5 h-3.5" /> : <EyeSlashIcon className="w-3.5 h-3.5" />}
                            <span>Heatmap</span>
                        </button>
                    )}
                </div>
              </div>
            </div>
            <div className="p-4">
              <div className="aspect-video bg-black rounded-lg overflow-hidden relative">
                {emissionLoading && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 z-10">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-red-500 border-t-transparent mb-4"></div>
                    <p className="text-white text-sm">Loading video...</p>
                    <p className="text-gray-400 text-xs mt-1">Transcoding if needed</p>
                  </div>
                )}
                {emissionError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 z-10">
                    <p className="text-red-400 text-sm">Failed to load video</p>
                    <button 
                      onClick={() => {
                        setEmissionError(false);
                        setEmissionLoading(true);
                        if (emissionVideoRef.current) {
                          emissionVideoRef.current.load();
                        }
                      }}
                      className="mt-2 px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                    >
                      Retry
                    </button>
                  </div>
                )}
                <video
                  ref={emissionVideoRef}
                  className="w-full h-full object-contain"
                  src={emissionVideoUrl}
                  preload="auto"
                  onLoadedData={() => setEmissionLoading(false)}
                  onCanPlay={() => setEmissionLoading(false)}
                  onError={() => {
                    setEmissionLoading(false);
                    setEmissionError(true);
                  }}
                />
                
                {/* Heatmap Overlay */}
                {showHeatmap && currentDiffImage && (
                    <div className="absolute inset-0 z-20 pointer-events-none opacity-80 mix-blend-screen">
                        <img 
                            src={`http://localhost:8001${currentDiffImage}`} 
                            alt="Difference Heatmap" 
                            className="w-full h-full object-contain"
                        />
                        <div className="absolute top-2 right-2 bg-red-600 text-white text-[10px] px-1.5 py-0.5 rounded shadow-sm opacity-90 font-bold uppercase tracking-wider">
                            DIFF
                        </div>
                    </div>
                )}

              </div>
            </div>
            {/* Emission Volume Control */}
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 flex items-center space-x-2">
              <SpeakerWaveIcon className="w-4 h-4 text-gray-500" />
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : emissionVolume}
                onChange={(e) => handleEmissionVolumeChange(Number(e.target.value))}
                className="w-24 h-1.5 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-red-600"
              />
              <span className="text-xs text-gray-500 w-8 tabular-nums font-medium">
                {Math.round((isMuted ? 0 : emissionVolume) * 100)}%
              </span>
            </div>
          </div>
        </div>

        {/* Synchronized Video Controls */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-start space-x-4 flex-grow">
              <button
                onClick={togglePlayPause}
                style={{ zIndex: 9999, position: 'relative' }}
                className="w-12 h-12 flex items-center justify-center bg-blue-500 hover:bg-blue-600 text-white rounded-full transition-colors flex-shrink-0 shadow-lg relative z-50"
              >
                {isPlaying ? (
                  <PauseIcon className="w-6 h-6" />
                ) : (
                  <PlayIcon className="w-6 h-6 ml-1" />
                )}
              </button>

              <div className="flex items-center space-x-2 flex-grow mx-4">
                {/* Time display moved inside slider row */}
                
                <div className="flex-grow flex flex-col">
                  {/* Main Slider Row - Height matched to button (h-12) for perfect alignment */}
                  <div className="h-12 flex items-center space-x-3">
                    <span className="text-sm text-gray-600 w-12 text-right font-mono">
                      {formatTime(currentTime)}
                    </span>
                    <input
                      type="range"
                      min="0"
                      max={duration || 100}
                      value={currentTime}
                      onChange={(e) => handleSeek(Number(e.target.value))}
                      className="flex-grow h-2 bg-gray-300 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <span className="text-sm text-gray-600 w-12 font-mono">
                      {formatTime(duration)}
                    </span>
                  </div>
                  
                  {/* Difference Tracks Container */}
                  <div className="mt-4 space-y-3 w-full">
                    
                    {/* 1. VIDEO Differences Track (RED) */}
                    <div className="relative h-4 w-full bg-red-50 rounded border border-red-100 flex items-center overflow-hidden">
                      <span className="absolute -left-16 text-xs font-bold text-red-600 uppercase w-14 text-right">Video</span>
                      {duration > 0 && differences.map((diff, index) => {
                        const position = (diff.timestamp_seconds / duration) * 100;
                        return (
                          <div
                            key={`video-${index}`}
                            onClick={() => {
                              jumpToDifference(diff.timestamp_seconds);
                              setInspectorInitialTimestamp(diff.timestamp_seconds);
                              setShowInspector(true);
                            }}
                            className="absolute bg-red-600 hover:bg-red-700 cursor-pointer z-10"
                            style={{ 
                                left: `${position}%`, 
                                width: '2px', 
                                height: '100%' 
                            }}
                            title={`🎬 Video Diff: ${formatTime(diff.timestamp_seconds)}`}
                          />
                        );
                      })}
                    </div>



                    {/* 3. AUDIO Differences Track (BLUE) - Placeholder for now */}
                    <div className="relative h-4 w-full bg-blue-50 rounded border border-blue-100 flex items-center">
                      <span className="absolute -left-16 text-xs font-bold text-blue-600 uppercase w-14 text-right">Audio</span>
                      {/* Placeholder markers or if we had timestamps */}
                    </div>
                  </div>
                </div>

                {/* Duration display moved inside slider row */}
              </div>
            </div>

            <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
              <button
                onClick={toggleMute}
                className={`p-2 rounded-lg transition-colors ${isMuted ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                title="Global Mute"
              >
                {isMuted ? (
                  <SpeakerXMarkIcon className="w-5 h-5" />
                ) : (
                  <SpeakerWaveIcon className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {/* Timeline Legend */}
          <div className="flex items-center justify-center gap-6 text-xs text-gray-500 mt-6">
            <div className="flex items-center">
              <div className="w-2.5 h-2.5 bg-red-500 rounded-full mr-2"></div>
              Różnice Video
            </div>

            <div className="flex items-center">
              <div className="w-1 h-4 bg-blue-500 mr-2"></div>
              Różnice Audio
            </div>
          </div>

          {/* Difference Jump Buttons Removed as requested */}
        </div>

        {/* Results Panel */}
        {showResults && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <DocumentChartBarIcon className="w-6 h-6 text-blue-500 mr-3" />
                <h2 className="text-xl font-semibold text-gray-900">
                  Comparison Results
                </h2>
                {loading && <span className="ml-2 text-gray-500">(Loading...)</span>}
              </div>
              
              <div className="flex items-center">
                 {/* Print Button - visible on screen, hidden on print */}
                 <button 
                    onClick={() => window.print()} 
                    className="flex items-center space-x-1 px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 print:hidden mr-4 shadow-sm"
                 >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
                    </svg>
                    <span>Export PDF</span>
                 </button>
              </div>

              {/* Re-analyze dropdown with current level indicator */}
              <div className="flex items-center gap-2 print:hidden">
                <span className="text-sm text-gray-500">
                  Current: <span className="font-semibold capitalize">{job.sensitivity_level || "medium"}</span>
                </span>
                <span className="text-gray-300">|</span>
                <span className="text-sm text-gray-500">Re-analyze:</span>
                {(["low", "medium", "high"] as const).map((level) => {
                  const isCurrent = (job.sensitivity_level || "medium") === level;
                  return (
                    <button
                      key={level}
                      disabled={reanalyzing || isCurrent}
                      onClick={async () => {
                        setReanalyzing(true);
                        try {
                          const formData = new FormData();
                          formData.append("sensitivity_level", level);
                          const response = await fetch(
                            `http://localhost:8001/api/v1/compare/${job.id}/reanalyze`,
                            { method: "POST", body: formData }
                          );
                          if (response.ok) {
                            // Reload to reset app state and show list
                            window.location.reload();
                          } else {
                            const errText = await response.text();
                            console.error("Failed to start re-analysis", errText);
                            alert("Failed to start re-analysis: " + errText);
                          }
                        } catch (err) {
                          console.error("Error in re-analysis:", err);
                          alert("Error starting re-analysis. Check console.");
                        } finally {
                          setReanalyzing(false);
                        }
                      }}
                      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        level === "low" ? "bg-green-100 text-green-700 hover:bg-green-200" :
                        level === "medium" ? "bg-amber-100 text-amber-700 hover:bg-amber-200" :
                        "bg-red-100 text-red-700 hover:bg-red-200"
                      } ${isCurrent ? "ring-2 ring-offset-1 ring-blue-500 font-bold" : ""} ${
                        reanalyzing || isCurrent ? "opacity-50 cursor-not-allowed" : ""
                      }`}
                    >
                      {level === "low" ? "Low" : level === "medium" ? "Medium" : "High"}
                      {isCurrent && " ✓"}
                    </button>
                  );
                })}
              </div>
            </div>

            {results ? (
              <>
                {/* Similarity Scores */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  {/* Overall Similarity */}
                  <div className="text-center p-6 bg-blue-50 rounded-xl">
                    <div className="text-4xl font-bold text-blue-600 mb-2">
                      {Math.round((overallScore || 0) * 100)}%
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Overall Similarity
                    </h3>
                    <p className="text-sm text-gray-600">Combined analysis</p>
                  </div>

                  {/* Video Similarity */}
                  <div className="text-center p-6 bg-purple-50 rounded-xl">
                    <div className="text-4xl font-bold text-purple-600 mb-2">
                      {Math.round((videoSimilarity || 0) * 100)}%
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Video Similarity
                    </h3>
                    <p className="text-sm text-gray-600">
                      {videoDifferences} / {totalFrames} frames differ
                    </p>
                  </div>

                  {/* Audio Similarity */}
                  <div className="text-center p-6 bg-green-50 rounded-xl">
                    <div className="text-4xl font-bold text-green-600 mb-2">
                      {Math.round((audioSimilarity || 0) * 100)}%
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Audio Similarity
                    </h3>
                    <p className="text-sm text-gray-600">Spectral analysis</p>
                  </div>
                </div>


                {/* Audio Results Section */}
                {results.overall_result?.report_data?.audio?.loudness && (() => {
                  const audio = results.overall_result.report_data.audio;
                  const loudness = audio.loudness;
                  const similarity = audio.similarity;
                  
                  return (
                    <div id="audio-results-section" className="mb-8">
                      {/* Header */}
                      <div className="flex items-center justify-between mb-4 p-4 bg-purple-50 rounded-t-xl border border-purple-200">
                        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                          🔊 Audio Comparison
                          {audio.has_loudness_differences ? (
                            <span className="ml-2 px-3 py-1 bg-red-100 text-red-700 text-sm rounded-full font-medium">
                              Różnice w głośności
                            </span>
                          ) : (
                            <span className="ml-2 px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full font-medium">
                              ✓ Głośność zgodna
                            </span>
                          )}
                        </h3>
                        {similarity && (
                          <span className="text-2xl font-bold text-purple-600">
                            {Math.round((similarity.overall_audio_similarity || 0) * 100)}% match
                          </span>
                        )}
                      </div>
                      
                      {/* Two Panel View - LUFS */}
                      <div className="grid grid-cols-2 gap-0 border border-gray-200 rounded-b-xl overflow-hidden">
                        {/* Acceptance LUFS */}
                        <div className="border-r border-gray-200">
                          <div className="bg-green-500 text-white px-4 py-2 font-semibold text-center">
                            📊 Acceptance LUFS
                          </div>
                          <div className="p-4 bg-gray-50">
                            {loudness?.acceptance ? (
                              <>
                                <div className="text-center mb-3">
                                  <span className="text-4xl font-bold text-gray-800">
                                    {loudness.acceptance.integrated_lufs}
                                  </span>
                                  <span className="text-lg text-gray-500 ml-1">LUFS</span>
                                </div>
                                <div className="text-sm text-gray-600 space-y-1">
                                  <div className="flex justify-between">
                                    <span>True Peak:</span>
                                    <span className="font-medium">{loudness.acceptance.true_peak_db} dB</span>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <p className="text-gray-400 text-sm italic">Brak danych</p>
                            )}
                          </div>
                        </div>
                        
                        {/* Emission LUFS */}
                        <div>
                          <div className="bg-red-500 text-white px-4 py-2 font-semibold text-center">
                            📊 Emission LUFS
                          </div>
                          <div className="p-4 bg-gray-50">
                            {loudness?.emission ? (
                              <>
                                <div className="text-center mb-3">
                                  <span className="text-4xl font-bold text-gray-800">
                                    {loudness.emission.integrated_lufs}
                                  </span>
                                  <span className="text-lg text-gray-500 ml-1">LUFS</span>
                                </div>
                                <div className="text-sm text-gray-600 space-y-1">
                                  <div className="flex justify-between">
                                    <span>True Peak:</span>
                                    <span className="font-medium">{loudness.emission.true_peak_db} dB</span>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <p className="text-gray-400 text-sm italic">Brak danych</p>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {/* Comparison Summary */}
                      {loudness?.comparison && (
                        <div className="mt-3 p-4 bg-gray-100 rounded-lg">
                          <div className="grid grid-cols-2 gap-4 text-center">
                            <div className={`p-3 rounded-lg ${loudness.comparison.is_lufs_match ? 'bg-green-100' : 'bg-red-100'}`}>
                              <div className="text-sm text-gray-600">Różnica LUFS</div>
                              <div className={`text-2xl font-bold ${loudness.comparison.is_lufs_match ? 'text-green-700' : 'text-red-700'}`}>
                                {loudness.comparison.lufs_difference > 0 ? '+' : ''}{loudness.comparison.lufs_difference} LU
                              </div>
                              <div className="text-xs text-gray-500">
                                {loudness.comparison.is_lufs_match ? '✓ W tolerancji ±1 LU' : '⚠️ Poza tolerancją'}
                              </div>
                            </div>
                            <div className={`p-3 rounded-lg ${loudness.comparison.is_peak_match ? 'bg-green-100' : 'bg-red-100'}`}>
                              <div className="text-sm text-gray-600">Różnica Peak</div>
                              <div className={`text-2xl font-bold ${loudness.comparison.is_peak_match ? 'text-green-700' : 'text-red-700'}`}>
                                {loudness.comparison.peak_difference_db > 0 ? '+' : ''}{loudness.comparison.peak_difference_db} dB
                              </div>
                              <div className="text-xs text-gray-500">
                                {loudness.comparison.is_peak_match ? '✓ W tolerancji ±1 dB' : '⚠️ Poza tolerancją'}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Source Separation Results (HIGH sensitivity only) */}
                      {audio.source_separation && (
                        <div className="mt-4 p-4 bg-indigo-50 rounded-lg border border-indigo-200">
                          <h4 className="text-sm font-semibold text-gray-700 mb-3">
                            🎭 Source Separation (Demucs)
                          </h4>
                          <div className="grid grid-cols-2 gap-4">
                            {/* Acceptance */}
                            <div className="text-center">
                              <div className="text-xs text-gray-500 mb-1">Acceptance</div>
                              <div className="flex items-center justify-center gap-2">
                                <span className="text-lg font-bold text-indigo-600">
                                  🎤 {Math.round((audio.source_separation.acceptance?.vocals_proportion || 0) * 100)}%
                                </span>
                                <span className="text-lg font-bold text-purple-600">
                                  🎵 {Math.round((audio.source_separation.acceptance?.music_proportion || 0) * 100)}%
                                </span>
                              </div>
                              <div className="text-xs text-gray-400 mt-1">
                                {audio.source_separation.acceptance?.has_vocals ? '✓ Has vocals' : 'No vocals detected'}
                              </div>
                            </div>
                            {/* Emission */}
                            <div className="text-center">
                              <div className="text-xs text-gray-500 mb-1">Emission</div>
                              <div className="flex items-center justify-center gap-2">
                                <span className="text-lg font-bold text-indigo-600">
                                  🎤 {Math.round((audio.source_separation.emission?.vocals_proportion || 0) * 100)}%
                                </span>
                                <span className="text-lg font-bold text-purple-600">
                                  🎵 {Math.round((audio.source_separation.emission?.music_proportion || 0) * 100)}%
                                </span>
                              </div>
                              <div className="text-xs text-gray-400 mt-1">
                                {audio.source_separation.emission?.has_vocals ? '✓ Has vocals' : 'No vocals detected'}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Voiceover Comparison (if both have vocals) */}
                      {audio.voiceover && (
                        <div className={`mt-4 p-4 rounded-lg border ${audio.voiceover.is_same_voice ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'}`}>
                          <h4 className="text-sm font-semibold text-gray-700 mb-3">
                            🎤 Voiceover Comparison
                          </h4>
                          <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                              <div className="text-xs text-gray-500 mb-1">Voice Similarity</div>
                              <div className={`text-2xl font-bold ${audio.voiceover.is_same_voice ? 'text-green-600' : 'text-yellow-600'}`}>
                                {Math.round(audio.voiceover.voice_similarity * 100)}%
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">Same Voice?</div>
                              <div className={`text-lg font-bold ${audio.voiceover.is_same_voice ? 'text-green-600' : 'text-yellow-600'}`}>
                                {audio.voiceover.is_same_voice ? '✓ TAK' : '⚠️ NIE'}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">Sync Status</div>
                              <div className={`text-lg font-bold ${audio.voiceover.timing?.is_synced ? 'text-green-600' : 'text-yellow-600'}`}>
                                {audio.voiceover.timing?.is_synced ? '✓ Synced' : `${audio.voiceover.timing?.average_offset_seconds?.toFixed(2)}s offset`}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Transcript Comparison (HIGH sensitivity only) */}
                      {audio.speech_to_text && (
                        <div className="mt-4 p-4 bg-teal-50 rounded-lg border border-teal-200">
                          <h4 className="flex items-center text-sm font-semibold text-gray-700 mb-3">
                            📝 Transcript Comparison (Whisper)
                            <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${audio.speech_to_text.is_text_match ? 'bg-green-100 text-green-800' : 'bg-orange-100 text-orange-800'}`}>
                              {Math.round(audio.speech_to_text.text_similarity * 100)}% match
                            </span>
                          </h4>
                          
                          <div className="space-y-4">
                            {/* Comparison View */}
                            {audio.speech_to_text.comparison && audio.speech_to_text.comparison.total_differences > 0 ? (
                              <div className="bg-white p-3 rounded border border-gray-200 max-h-40 overflow-y-auto">
                                <div className="text-xs text-gray-500 mb-2 font-medium">Word Differences Detected:</div>
                                {audio.speech_to_text.comparison.word_differences.map((diff, idx) => (
                                  <div key={idx} className="mb-2 text-sm pl-2 border-l-2 border-red-300">
                                    <div className="flex gap-2">
                                      <span className="text-gray-400 w-16 text-xs uppercase">{diff.type}</span>
                                      <div className="flex-1">
                                        {diff.acceptance && (
                                          <div className="text-green-700 bg-green-50 px-1 rounded inline-block mr-1">
                                            {diff.acceptance}
                                          </div>
                                        )}
                                        {diff.emission && (
                                          <div className="text-red-700 bg-red-50 px-1 rounded inline-block decoration-slice">
                                            {diff.emission}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="bg-green-50 p-3 rounded text-green-700 text-sm flex items-center">
                                <span className="mr-2">✓</span> No text differences found
                              </div>
                            )}

                            {/* OCR Timeline (SRT Style) */}
                            {results?.overall_result?.report_data?.ocr?.timeline && results.overall_result.report_data.ocr.timeline.length > 0 ? (
                              <div className="mt-4">
                                <h4 className="text-sm font-semibold text-gray-700 mb-2">Detected Text Timeline</h4>
                                <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg">
                                  <table className="min-w-full divide-y divide-gray-200 text-xs">
                                    <thead className="bg-gray-50 sticky top-0">
                                      <tr>
                                        <th scope="col" className="px-3 py-2 text-left font-medium text-gray-500 uppercase tracking-wider w-20">Time</th>
                                        <th scope="col" className="px-3 py-2 text-left font-medium text-gray-500 uppercase tracking-wider w-24">Source</th>
                                        <th scope="col" className="px-3 py-2 text-left font-medium text-gray-500 uppercase tracking-wider">Text</th>
                                      </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                      {results.overall_result.report_data.ocr.timeline.map((item: any, idx: number) => (
                                        <tr 
                                          key={idx} 
                                          className={`hover:bg-gray-50 cursor-pointer transition-colors ${item.is_difference ? 'bg-orange-50' : ''}`}
                                          onClick={() => jumpToDifference(item.timestamp)}
                                        >
                                          <td className="px-3 py-2 whitespace-nowrap font-mono text-gray-500">
                                            {formatTime(item.timestamp)}
                                          </td>
                                          <td className="px-3 py-2 whitespace-nowrap">
                                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium ${
                                              item.source === 'acceptance' 
                                                ? 'bg-green-100 text-green-800' 
                                                : 'bg-red-100 text-red-800'
                                            }`}>
                                              {item.source === 'acceptance' ? 'Acceptance' : 'Emission'}
                                            </span>
                                          </td>
                                          <td className="px-3 py-2 text-gray-900 break-words max-w-lg">
                                            {item.text}
                                            {item.is_difference && (
                                              <span className="ml-2 text-orange-600 font-bold" title="Missing in other video at this time">⚠️</span>
                                            )}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            ) : (
                              /* Legacy Fallback if timeline missing */
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <div className="text-xs text-gray-500 mb-1">Unique Acceptance Text</div>
                                  <div className="p-2 bg-white rounded border border-gray-200 text-xs text-gray-600 h-32 overflow-y-auto italic">
                                    {results?.overall_result?.report_data?.ocr?.only_in_acceptance?.join('\n') || "None"}
                                  </div>
                                </div>
                                <div>
                                  <div className="text-xs text-gray-500 mb-1">Unique Emission Text</div>
                                  <div className="p-2 bg-white rounded border border-gray-200 text-xs text-gray-600 h-32 overflow-y-auto italic">
                                     {results?.overall_result?.report_data?.ocr?.only_in_emission?.join('\n') || "None"}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Detected Differences */}
                {differences.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">
                      Detected Differences ({differences.length})
                    </h4>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {differences.map((diff, index) => (
                        <div
                          key={index}
                          className="p-3 bg-orange-50 border-l-4 border-orange-400 rounded-lg cursor-pointer hover:bg-orange-100 transition-colors"
                          onClick={() => jumpToDifference(diff.timestamp_seconds)}
                        >
                          <div className="flex justify-between items-center">
                            <span className="text-sm font-medium text-orange-800">
                              {diff.difference_type.replace("_", " ")}
                            </span>
                            <span className="text-xs text-orange-600">
                              {Math.round(diff.confidence * 100)}% confidence
                            </span>
                          </div>
                          <p className="text-xs text-orange-700 mt-1">
                            At {formatTime(diff.timestamp_seconds)} 
                            {diff.duration_seconds > 0 && ` (${diff.duration_seconds.toFixed(1)}s)`}
                            {diff.description && ` - ${diff.description}`}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : !loading ? (
              <div className="text-center py-8 text-gray-500">
                {job.status === "completed" 
                  ? "No detailed results available"
                  : `Job status: ${job.status}. Results will be available after completion.`
                }
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Frame Comparison Modal (REMOVED: Replaced by DifferenceInspector) */}
    </div>
  );
};

export default VideoComparison;
