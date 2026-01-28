// frontend/src/components/VideoComparison.tsx
import React, { useState, useEffect, useRef } from "react";
import { ComparisonJob } from "../types";
import {
  PlayIcon,
  PauseIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ChartBarSquareIcon,
  DocumentChartBarIcon,
  ForwardIcon,
} from "@heroicons/react/24/outline";

interface VideoComparisonProps {
  job: ComparisonJob;
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
      ocr?: {
        text_similarity: number | null;
        has_differences: boolean;
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

const VideoComparison: React.FC<VideoComparisonProps> = ({ job }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<ApiResults | null>(null);
  const [selectedDifference, setSelectedDifference] = useState<{
    timestamp_seconds: number;
    difference_type: string;
    confidence: number;
  } | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  
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

  const handleVolumeChange = (newVolume: number) => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => {
      if (video) {
        video.volume = newVolume;
      }
    });
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
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
            </div>
          </div>
        </div>

        {/* Video Players - Side by Side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
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
                <p className="text-xs text-gray-600 mt-1 break-all leading-tight" title={job.acceptance_file?.original_name || job.acceptance_file?.filename || ''}>
                  {job.acceptance_file?.original_name || job.acceptance_file?.filename || 'Loading...'}
                </p>
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
                <p className="text-xs text-gray-600 mt-1 break-all leading-tight" title={job.emission_file?.original_name || job.emission_file?.filename || ''}>
                  {job.emission_file?.original_name || job.emission_file?.filename || 'Loading...'}
                </p>
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
              </div>
            </div>
          </div>
        </div>

        {/* Synchronized Video Controls */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={togglePlayPause}
                className="p-3 bg-blue-500 text-white rounded-full hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
              >
                {isPlaying ? (
                  <PauseIcon className="w-6 h-6" />
                ) : (
                  <PlayIcon className="w-6 h-6" />
                )}
              </button>

              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600 w-12">
                  {formatTime(currentTime)}
                </span>
                {/* Enhanced Timeline with Difference Markers */}
                <div className="w-64 relative">
                  <input
                    type="range"
                    min="0"
                    max={duration || 100}
                    value={currentTime}
                    onChange={(e) => handleSeek(Number(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500 relative z-10"
                  />
                  {/* Video Difference Markers (RED) */}
                  {duration > 0 && differences.map((diff, index) => {
                    const position = (diff.timestamp_seconds / duration) * 100;
                    return (
                      <button
                        key={`video-${index}`}
                        onClick={() => {
                          jumpToDifference(diff.timestamp_seconds);
                          setSelectedDifference(diff);
                        }}
                        className="absolute top-0 w-3 h-3 bg-red-500 rounded-full border-2 border-white shadow-md hover:scale-125 transition-transform z-20 cursor-pointer"
                        style={{ left: `calc(${position}% - 6px)`, top: '-2px' }}
                        title={`🎬 ${formatTime(diff.timestamp_seconds)} - ${diff.difference_type}`}
                      />
                    );
                  })}
                  {/* OCR Text Difference Markers (AMBER) */}
                  {duration > 0 && results?.overall_result?.report_data?.ocr?.differences?.map((ocrDiff, index) => {
                    const position = (ocrDiff.timestamp / duration) * 100;
                    return (
                      <button
                        key={`ocr-${index}`}
                        onClick={() => {
                          jumpToDifference(ocrDiff.timestamp);
                          // Scroll to OCR section
                          document.getElementById('ocr-results-section')?.scrollIntoView({ behavior: 'smooth' });
                        }}
                        className="absolute top-0 w-3 h-3 bg-amber-500 rounded-full border-2 border-white shadow-md hover:scale-125 transition-transform z-20 cursor-pointer"
                        style={{ left: `calc(${position}% - 6px)`, top: '-2px' }}
                        title={`🔤 OCR @ ${formatTime(ocrDiff.timestamp)} - ${ocrDiff.text.substring(0, 30)}...`}
                      />
                    );
                  })}
                </div>
                <span className="text-sm text-gray-600 w-12">
                  {formatTime(duration)}
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <button
                  onClick={toggleMute}
                  className="p-2 text-gray-600 hover:text-gray-800 focus:outline-none rounded-lg transition-colors"
                >
                  {isMuted ? (
                    <SpeakerXMarkIcon className="w-5 h-5" />
                  ) : (
                    <SpeakerWaveIcon className="w-5 h-5" />
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => handleVolumeChange(Number(e.target.value))}
                  className="w-20 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Timeline Legend */}
          {(differences.length > 0 || results?.overall_result?.report_data?.ocr?.differences?.length) && (
            <div className="flex items-center justify-center gap-4 text-xs text-gray-500 mt-2">
              {differences.length > 0 && (
                <div className="flex items-center">
                  <div className="w-2.5 h-2.5 bg-red-500 rounded-full mr-1"></div>
                  Różnica video
                </div>
              )}
              {(results?.overall_result?.report_data?.ocr?.differences?.length ?? 0) > 0 && (
                <div className="flex items-center">
                  <div className="w-2.5 h-2.5 bg-amber-500 rounded-full mr-1"></div>
                  Różnica OCR
                </div>
              )}
            </div>
          )}

          {/* Difference Jump Buttons */}
          {differences.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <p className="text-sm font-medium text-gray-700 mb-2">
                Jump to difference:
              </p>
              <div className="flex flex-wrap gap-2">
                {differences.slice(0, 10).map((diff, index) => (
                  <button
                    key={index}
                    onClick={() => jumpToDifference(diff.timestamp_seconds)}
                    className="inline-flex items-center px-3 py-1.5 bg-orange-100 text-orange-800 text-sm rounded-full hover:bg-orange-200 transition-colors"
                  >
                    <ForwardIcon className="w-3 h-3 mr-1" />
                    {formatTime(diff.timestamp_seconds)}
                    <span className="ml-1 text-xs opacity-75">
                      ({diff.difference_type.replace("_", " ")})
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
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
              
              {/* Re-analyze dropdown with current level indicator */}
              <div className="flex items-center gap-2">
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
                            // Auto-reload page to show new job in list
                            window.location.reload();
                          } else {
                            console.error("Failed to start re-analysis");
                          }
                        } catch (err) {
                          console.error("Error:", err);
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

                {/* OCR Text Detection Results - Two Panel View */}
                {results.overall_result?.report_data?.ocr && (() => {
                  const ocr = results.overall_result.report_data.ocr;
                  const totalTexts = ocr.common_texts.length + ocr.only_in_acceptance.length + ocr.only_in_emission.length;
                  const mismatchCount = ocr.only_in_acceptance.length + ocr.only_in_emission.length;
                  const mismatchPercent = totalTexts > 0 ? Math.round((mismatchCount / totalTexts) * 100) : 0;
                  
                  return (
                    <div id="ocr-results-section" className="mb-8">
                      {/* Header */}
                      <div className="flex items-center justify-between mb-4 p-4 bg-amber-50 rounded-t-xl border border-amber-200">
                        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                          🔤 OCR Text Detection
                          {ocr.has_differences ? (
                            <span className="ml-2 px-3 py-1 bg-red-100 text-red-700 text-sm rounded-full font-medium">
                              {mismatchPercent}% niezgodności ({mismatchCount} różnic)
                            </span>
                          ) : (
                            <span className="ml-2 px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full font-medium">
                              ✓ 100% zgodności
                            </span>
                          )}
                        </h3>
                        <span className="text-2xl font-bold text-amber-600">
                          {Math.round((ocr.text_similarity || 1) * 100)}% match
                        </span>
                      </div>
                      
                      {/* Two Panel View */}
                      <div className="grid grid-cols-2 gap-0 border border-gray-200 rounded-b-xl overflow-hidden">
                        {/* Acceptance Panel */}
                        <div className="border-r border-gray-200">
                          <div className="bg-green-500 text-white px-4 py-2 font-semibold text-center">
                            📄 Acceptance
                          </div>
                          <div className="p-4 bg-gray-50 min-h-[200px] max-h-[400px] overflow-y-auto">
                            {/* Common texts */}
                            {ocr.common_texts.map((text, i) => (
                              <div key={`common-a-${i}`} className="mb-2 p-2 bg-white rounded border border-gray-200 text-sm text-gray-700">
                                {text}
                              </div>
                            ))}
                            {/* Only in Acceptance - highlighted green */}
                            {ocr.only_in_acceptance.map((text, i) => (
                              <div key={`only-a-${i}`} className="mb-2 p-2 bg-green-100 rounded border-2 border-green-400 text-sm text-green-800 font-medium">
                                <span className="text-xs bg-green-500 text-white px-1 py-0.5 rounded mr-2">UNIQUE</span>
                                {text}
                              </div>
                            ))}
                            {ocr.common_texts.length === 0 && ocr.only_in_acceptance.length === 0 && (
                              <p className="text-gray-400 text-sm italic">Brak wykrytych tekstów</p>
                            )}
                          </div>
                        </div>
                        
                        {/* Emission Panel */}
                        <div>
                          <div className="bg-red-500 text-white px-4 py-2 font-semibold text-center">
                            📄 Emission
                          </div>
                          <div className="p-4 bg-gray-50 min-h-[200px] max-h-[400px] overflow-y-auto">
                            {/* Common texts */}
                            {ocr.common_texts.map((text, i) => (
                              <div key={`common-e-${i}`} className="mb-2 p-2 bg-white rounded border border-gray-200 text-sm text-gray-700">
                                {text}
                              </div>
                            ))}
                            {/* Only in Emission - highlighted red */}
                            {ocr.only_in_emission.map((text, i) => (
                              <div key={`only-e-${i}`} className="mb-2 p-2 bg-red-100 rounded border-2 border-red-400 text-sm text-red-800 font-medium">
                                <span className="text-xs bg-red-500 text-white px-1 py-0.5 rounded mr-2">UNIQUE</span>
                                {text}
                              </div>
                            ))}
                            {ocr.common_texts.length === 0 && ocr.only_in_emission.length === 0 && (
                              <p className="text-gray-400 text-sm italic">Brak wykrytych tekstów</p>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {/* Legend */}
                      <div className="flex items-center justify-center gap-6 mt-3 text-xs text-gray-500">
                        <div className="flex items-center">
                          <div className="w-3 h-3 bg-white border border-gray-300 rounded mr-1"></div>
                          Tekst wspólny
                        </div>
                        <div className="flex items-center">
                          <div className="w-3 h-3 bg-green-100 border-2 border-green-400 rounded mr-1"></div>
                          Tylko w Acceptance
                        </div>
                        <div className="flex items-center">
                          <div className="w-3 h-3 bg-red-100 border-2 border-red-400 rounded mr-1"></div>
                          Tylko w Emission
                        </div>
                      </div>
                    </div>
                  );
                })()}

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

      {/* Frame Comparison Modal */}
      {selectedDifference && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-[90vw] max-w-6xl max-h-[90vh] overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold">🔍 Porównanie klatek</h2>
                <p className="text-blue-100 text-sm">
                  Czas: {formatTime(selectedDifference.timestamp_seconds)} | 
                  Typ: {selectedDifference.difference_type.replace("_", " ")} | 
                  Pewność: {Math.round(selectedDifference.confidence * 100)}%
                </p>
              </div>
              <button
                onClick={() => setSelectedDifference(null)}
                className="p-2 hover:bg-white/20 rounded-lg transition-colors"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Side-by-side videos */}
            <div className="grid grid-cols-2 gap-0 border-b border-gray-200">
              {/* Acceptance Frame */}
              <div className="border-r border-gray-200">
                <div className="bg-green-500 text-white px-4 py-2 text-center font-semibold">
                  📄 Acceptance
                </div>
                <div className="p-4 bg-gray-100">
                  <video
                    ref={acceptanceVideoRef}
                    src={acceptanceVideoUrl}
                    className="w-full rounded-lg shadow-md"
                    muted
                  />
                </div>
              </div>
              
              {/* Emission Frame */}
              <div>
                <div className="bg-red-500 text-white px-4 py-2 text-center font-semibold">
                  📄 Emission
                </div>
                <div className="p-4 bg-gray-100">
                  <video
                    ref={emissionVideoRef}
                    src={emissionVideoUrl}
                    className="w-full rounded-lg shadow-md"
                    muted
                  />
                </div>
              </div>
            </div>
            
            {/* Navigation */}
            <div className="px-6 py-4 bg-gray-50 flex items-center justify-between">
              <button
                onClick={() => {
                  const currentIndex = differences.findIndex(
                    d => d.timestamp_seconds === selectedDifference.timestamp_seconds
                  );
                  if (currentIndex > 0) {
                    const prevDiff = differences[currentIndex - 1];
                    setSelectedDifference(prevDiff);
                    jumpToDifference(prevDiff.timestamp_seconds);
                  }
                }}
                disabled={differences.findIndex(d => d.timestamp_seconds === selectedDifference.timestamp_seconds) === 0}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center"
              >
                ← Poprzednia różnica
              </button>
              
              <div className="text-center">
                <span className="text-sm text-gray-500">
                  Różnica {differences.findIndex(d => d.timestamp_seconds === selectedDifference.timestamp_seconds) + 1} z {differences.length}
                </span>
              </div>
              
              <button
                onClick={() => {
                  const currentIndex = differences.findIndex(
                    d => d.timestamp_seconds === selectedDifference.timestamp_seconds
                  );
                  if (currentIndex < differences.length - 1) {
                    const nextDiff = differences[currentIndex + 1];
                    setSelectedDifference(nextDiff);
                    jumpToDifference(nextDiff.timestamp_seconds);
                  }
                }}
                disabled={differences.findIndex(d => d.timestamp_seconds === selectedDifference.timestamp_seconds) === differences.length - 1}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center"
              >
                Następna różnica →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoComparison;
