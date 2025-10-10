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
} from "@heroicons/react/24/outline";

interface VideoComparisonProps {
  job: ComparisonJob;
}

// Prostsze typy mockowe na potrzeby komponentu
interface MockVideoResult {
  ssim_score: number;
  histogram_correlation: number;
  phash_similarity: number;
  edge_similarity: number;
  frame_differences: MockFrameDifference[];
}

interface MockAudioResult {
  spectral_similarity: number;
  mfcc_similarity: number;
  perceptual_similarity: number;
  temporal_differences: MockTemporalDifference[];
}

interface MockFrameDifference {
  timestamp: number;
  confidence: number;
  difference_type: string;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

interface MockTemporalDifference {
  start_time: number;
  end_time: number;
  confidence: number;
  difference_type: string;
}

interface MockComparisonResult {
  video_results: MockVideoResult;
  audio_results: MockAudioResult;
  overall_score: number;
  differences_found: boolean;
}

const VideoComparison: React.FC<VideoComparisonProps> = ({ job }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);

  // Mock results
  const mockResults: MockComparisonResult = {
    video_results: {
      ssim_score: 0.92,
      histogram_correlation: 0.96,
      phash_similarity: 0.94,
      edge_similarity: 0.93,
      frame_differences: [
        {
          timestamp: 2.5,
          confidence: 0.8,
          difference_type: "color_shift",
          bounding_box: { x: 100, y: 150, width: 50, height: 75 },
        },
        {
          timestamp: 5.2,
          confidence: 0.9,
          difference_type: "object_moved",
          bounding_box: { x: 200, y: 100, width: 80, height: 60 },
        },
      ],
    },
    audio_results: {
      spectral_similarity: 0.89,
      mfcc_similarity: 0.87,
      perceptual_similarity: 0.88,
      temporal_differences: [
        {
          start_time: 1.2,
          end_time: 1.8,
          confidence: 0.75,
          difference_type: "volume_change",
        },
        {
          start_time: 4.1,
          end_time: 4.9,
          confidence: 0.85,
          difference_type: "frequency_shift",
        },
      ],
    },
    overall_score: 0.91,
    differences_found: true,
  };

  // Processing stats
  const processingStats = {
    total_frames: 1500,
    processed_frames: 1500,
    processing_time: 45.6,
  };

  useEffect(() => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
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

  const togglePlayPause = () => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];

    if (isPlaying) {
      videos.forEach((video) => video?.pause());
    } else {
      videos.forEach((video) => video?.play());
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
      return {
        label: "Excellent Match",
        color: "text-green-600",
        bg: "bg-green-100",
      };
    if (similarity >= 0.9)
      return { label: "Good Match", color: "text-blue-600", bg: "bg-blue-100" };
    if (similarity >= 0.8)
      return {
        label: "Fair Match",
        color: "text-yellow-600",
        bg: "bg-yellow-100",
      };
    return { label: "Poor Match", color: "text-red-600", bg: "bg-red-100" };
  };

  const status = getOverallStatus(mockResults.overall_score);

  // Calculate average video similarity
  const videoSimilarity =
    (mockResults.video_results.ssim_score +
      mockResults.video_results.histogram_correlation +
      mockResults.video_results.phash_similarity +
      mockResults.video_results.edge_similarity) /
    4;

  // Calculate average audio similarity
  const audioSimilarity =
    (mockResults.audio_results.spectral_similarity +
      mockResults.audio_results.mfcc_similarity +
      mockResults.audio_results.perceptual_similarity) /
    3;

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
              <p className="text-gray-600">Cradle ID: {job.cradle_id}</p>
              {mockResults.differences_found && (
                <p className="text-sm text-orange-600 mt-1">
                  ⚠️ Differences detected (
                  {mockResults.video_results.frame_differences.length} video,{" "}
                  {mockResults.audio_results.temporal_differences.length} audio)
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

        {/* Video Players */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Acceptance Video */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  Acceptance Video
                </h3>
                <span className="text-sm text-gray-500">
                  File ID: {job.acceptance_file_id}
                </span>
              </div>
            </div>
            <div className="p-6">
              <div className="aspect-video bg-black rounded-lg overflow-hidden mb-4">
                <video
                  ref={acceptanceVideoRef}
                  className="w-full h-full object-contain"
                  src="https://www.w3schools.com/html/mov_bbb.mp4"
                />
              </div>
            </div>
          </div>

          {/* Emission Video */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  Emission Video
                </h3>
                <span className="text-sm text-gray-500">
                  File ID: {job.emission_file_id}
                </span>
              </div>
            </div>
            <div className="p-6">
              <div className="aspect-video bg-black rounded-lg overflow-hidden mb-4">
                <video
                  ref={emissionVideoRef}
                  className="w-full h-full object-contain"
                  src="https://www.w3schools.com/html/mov_bbb.mp4"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Video Controls */}
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
                <span className="text-sm text-gray-600">
                  {formatTime(currentTime)}
                </span>
                <div className="w-64">
                  <input
                    type="range"
                    min="0"
                    max={duration}
                    value={currentTime}
                    onChange={(e) => handleSeek(Number(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
                <span className="text-sm text-gray-600">
                  {formatTime(duration)}
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <button
                  onClick={toggleMute}
                  className="p-2 text-gray-600 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded-lg transition-colors"
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
                  className="w-20 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Results Panel */}
        {showResults && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center mb-6">
              <DocumentChartBarIcon className="w-6 h-6 text-blue-500 mr-3" />
              <h2 className="text-xl font-semibold text-gray-900">
                Comparison Results
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              {/* Overall Similarity */}
              <div className="text-center">
                <div className="relative inline-flex items-center justify-center w-32 h-32 mb-4">
                  <svg
                    className="w-32 h-32 transform -rotate-90"
                    viewBox="0 0 144 144"
                  >
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      className="text-gray-200"
                    />
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      strokeDasharray={`${2 * Math.PI * 56}`}
                      strokeDashoffset={`${
                        2 * Math.PI * 56 * (1 - mockResults.overall_score)
                      }`}
                      className="text-blue-500 transition-all duration-1000 ease-out"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-gray-900">
                      {Math.round(mockResults.overall_score * 100)}%
                    </span>
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Overall Similarity
                </h3>
                <p className="text-sm text-gray-600">
                  Combined video and audio analysis
                </p>
              </div>

              {/* Video Similarity */}
              <div className="text-center">
                <div className="relative inline-flex items-center justify-center w-32 h-32 mb-4">
                  <svg
                    className="w-32 h-32 transform -rotate-90"
                    viewBox="0 0 144 144"
                  >
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      className="text-gray-200"
                    />
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      strokeDasharray={`${2 * Math.PI * 56}`}
                      strokeDashoffset={`${
                        2 * Math.PI * 56 * (1 - videoSimilarity)
                      }`}
                      className="text-purple-500 transition-all duration-1000 ease-out"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-gray-900">
                      {Math.round(videoSimilarity * 100)}%
                    </span>
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Video Similarity
                </h3>
                <p className="text-sm text-gray-600">
                  Frame-by-frame comparison
                </p>
              </div>

              {/* Audio Similarity */}
              <div className="text-center">
                <div className="relative inline-flex items-center justify-center w-32 h-32 mb-4">
                  <svg
                    className="w-32 h-32 transform -rotate-90"
                    viewBox="0 0 144 144"
                  >
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      className="text-gray-200"
                    />
                    <circle
                      cx="72"
                      cy="72"
                      r="56"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="transparent"
                      strokeDasharray={`${2 * Math.PI * 56}`}
                      strokeDashoffset={`${
                        2 * Math.PI * 56 * (1 - audioSimilarity)
                      }`}
                      className="text-green-500 transition-all duration-1000 ease-out"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-gray-900">
                      {Math.round(audioSimilarity * 100)}%
                    </span>
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Audio Similarity
                </h3>
                <p className="text-sm text-gray-600">
                  Spectral and perceptual analysis
                </p>
              </div>
            </div>

            {/* Detailed Algorithm Results */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              {/* Video Algorithms */}
              <div>
                <h4 className="text-lg font-semibold text-gray-900 mb-4">
                  Video Analysis
                </h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      SSIM Score
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.video_results.ssim_score * 100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(mockResults.video_results.ssim_score * 100)}
                        %
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      Histogram Correlation
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.video_results.histogram_correlation *
                              100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.video_results.histogram_correlation * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      pHash Similarity
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.video_results.phash_similarity * 100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.video_results.phash_similarity * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      Edge Similarity
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.video_results.edge_similarity * 100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.video_results.edge_similarity * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Audio Algorithms */}
              <div>
                <h4 className="text-lg font-semibold text-gray-900 mb-4">
                  Audio Analysis
                </h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      Spectral Similarity
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.audio_results.spectral_similarity *
                              100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.audio_results.spectral_similarity * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      MFCC Similarity
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.audio_results.mfcc_similarity * 100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.audio_results.mfcc_similarity * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700">
                      Perceptual Similarity
                    </span>
                    <div className="flex items-center space-x-3">
                      <div className="w-24 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-500 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{
                            width: `${
                              mockResults.audio_results.perceptual_similarity *
                              100
                            }%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-gray-600 w-10 text-right">
                        {Math.round(
                          mockResults.audio_results.perceptual_similarity * 100
                        )}
                        %
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Detected Differences */}
            {mockResults.differences_found && (
              <div className="mb-8">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">
                  Detected Differences
                </h4>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Video Differences */}
                  <div>
                    <h5 className="text-md font-medium text-gray-700 mb-3">
                      Video Differences (
                      {mockResults.video_results.frame_differences.length})
                    </h5>
                    <div className="space-y-2">
                      {mockResults.video_results.frame_differences.map(
                        (diff: MockFrameDifference, index: number) => (
                          <div
                            key={index}
                            className="p-3 bg-red-50 border-l-4 border-red-400 rounded-lg"
                          >
                            <div className="flex justify-between items-center">
                              <span className="text-sm font-medium text-red-800">
                                {diff.difference_type.replace("_", " ")}
                              </span>
                              <span className="text-xs text-red-600">
                                {Math.round(diff.confidence * 100)}% confidence
                              </span>
                            </div>
                            <p className="text-xs text-red-700 mt-1">
                              At {diff.timestamp}s
                              {diff.bounding_box &&
                                ` - Region: ${diff.bounding_box.x},${diff.bounding_box.y} (${diff.bounding_box.width}×${diff.bounding_box.height})`}
                            </p>
                          </div>
                        )
                      )}
                    </div>
                  </div>

                  {/* Audio Differences */}
                  <div>
                    <h5 className="text-md font-medium text-gray-700 mb-3">
                      Audio Differences (
                      {mockResults.audio_results.temporal_differences.length})
                    </h5>
                    <div className="space-y-2">
                      {mockResults.audio_results.temporal_differences.map(
                        (diff: MockTemporalDifference, index: number) => (
                          <div
                            key={index}
                            className="p-3 bg-orange-50 border-l-4 border-orange-400 rounded-lg"
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
                              From {diff.start_time}s to {diff.end_time}s
                            </p>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Processing Stats */}
            {processingStats && ( // ✅ POPRAWKA
              <div className="bg-gray-50 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Processing Statistics
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {processingStats.total_frames?.toLocaleString() || "N/A"}
                    </div>
                    <div className="text-sm text-gray-600">Total Frames</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {processingStats.processed_frames?.toLocaleString() ||
                        "N/A"}
                    </div>
                    <div className="text-sm text-gray-600">
                      Processed Frames
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {processingStats.processing_time?.toFixed(1) || "N/A"}s
                    </div>
                    <div className="text-sm text-gray-600">Processing Time</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600">
                      N/A {/* FPS nie jest zdefiniowane w processingStats */}
                    </div>
                    <div className="text-sm text-gray-600">FPS</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoComparison;
