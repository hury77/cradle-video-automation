// frontend/src/components/VideoComparison.tsx
import React, { useState, useEffect, useRef, useMemo } from "react";
import WaveSurfer from 'wavesurfer.js';
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
  ChevronRightIcon,
} from "@heroicons/react/24/outline";
import DifferenceInspector from "./DifferenceInspector";
import QAVerdictPanel from "./QAVerdictPanel";

import { translations, Language } from "../utils/translations";

interface VideoComparisonProps {
  job: ComparisonJob;
  onJobReanalyzed?: () => void;
  onBackToDashboard?: () => void;
  lang?: Language;
  theme?: "dark" | "light";
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
        is_arpp_slate?: boolean;
        duration_difference?: number;
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
          detected_language?: string;
          comparison?: {
            word_differences: Array<{
              type: string;
              acceptance: string;
              emission: string;
            }>;
            segment_differences?: Array<{
                segment_idx: number;
                time_a: string;
                time_b: string;
                text_a: string;
                text_b: string;
            }>;
            total_differences: number;
          };
          timeline_data?: {
            acceptance_segments: Array<{ start: number; end: number; text: string }>;
            emission_segments: Array<{ start: number; end: number; text: string }>;
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

const VideoComparison: React.FC<VideoComparisonProps> = ({ job, onJobReanalyzed, onBackToDashboard, lang = "PL", theme = "dark" }) => {
  const t = translations[lang];
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [acceptanceVolume, setAcceptanceVolume] = useState(1);
  const [emissionVolume, setEmissionVolume] = useState(1);
  const [prevAcceptanceVol, setPrevAcceptanceVol] = useState(1);
  const [prevEmissionVol, setPrevEmissionVol] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // Build video URLs from job data
  // Use http://localhost:800X in dev to bypass webpack dev proxy for large media streams, relative in prod
  const baseUrl = (() => {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      const port = window.location.port;
      if (port === '3000' || port === '3001') {
        const backendPort = parseInt(port) + 5001;
        return `http://localhost:${backendPort}`;
      }
      return 'http://localhost:8001';
    }
    return '';
  })();
  const acceptanceVideoUrl = `${baseUrl}/api/v1/files/stream/${job.acceptance_file_id}`;
  const emissionVideoUrl = `${baseUrl}/api/v1/files/stream/${job.emission_file_id}`;

  // Sync heatmap with playback
  const [currentDiffImage, setCurrentDiffImage] = useState<string | null>(null);

  const [showResults, setShowResults] = useState(false);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<ApiResults | null>(null);
  // Inspector Modal State
  const [reanalyzing, setReanalyzing] = useState(false);

  // Calculate ARPP offsets
  const { acceptanceOffset, emissionOffset, displayDuration } = useMemo(() => {
    const reportData = results?.overall_result?.report_data;
    const isArpp = reportData?.video?.is_arpp_slate || false;
    
    // Fallback: detect via duration if backend report data is missing or legacy
    const durAcc = job.acceptance_file?.duration || 0;
    const durEmi = job.emission_file?.duration || 0;
    const durationDiff = Math.abs(durAcc - durEmi);
    const fallbackIsArpp = durationDiff >= 10.5 && durationDiff <= 11.5;
    
    const arppActive = isArpp || fallbackIsArpp;
    
    let accOffset = 0;
    let emiOffset = 0;
    
    if (arppActive) {
      if (durAcc > durEmi) {
        accOffset = 10.0;
        emiOffset = 0.0;
      } else {
        accOffset = 0.0;
        emiOffset = 10.0;
      }
    }
    
    // We override duration to be the commercial length (max duration - offset)
    const baseDuration = duration || Math.max(durAcc, durEmi);
    const commercialDuration = Math.max(0, baseDuration - Math.max(accOffset, emiOffset));
    
    return {
      acceptanceOffset: accOffset,
      emissionOffset: emiOffset,
      displayDuration: commercialDuration
    };
  }, [results, job, duration]);

  // Audio Visualization Refs
  const waveformRef = useRef<HTMLDivElement>(null);
  const emissionWaveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const emissionWavesurferRef = useRef<WaveSurfer | null>(null);

  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);
  
  // Waveform Error States
  
  // Waveform Error States
  const [waveformError, setWaveformError] = useState<string | null>(null);
  const [emissionWaveformError, setEmissionWaveformError] = useState<string | null>(null);

  // Extract Audio Segments for Timeline
  const audioDiffSegments = results?.overall_result?.report_data?.audio?.speech_to_text?.comparison?.segment_differences || [];
  const detectedLanguage = results?.overall_result?.report_data?.audio?.speech_to_text?.detected_language;

  // Initialize WaveSurfer
  useEffect(() => {
      // Helper: Create WaveSurfer with pre-fetched blob URL for reliable audio decoding.
      // WaveSurfer internally fetches the media element's `src` URL to decode audio.
      // For large files (37MB+), this internal fetch can fail/timeout.
      // Solution: pre-fetch as blob, create blob URL → WaveSurfer.load(blobUrl).
      const blobUrlsToCleanup: string[] = [];
      
      const initWaveSurfer = async (
          container: HTMLDivElement,
          mediaEl: HTMLVideoElement,
          videoUrl: string,
          colors: { wave: string; progress: string },
          label: string,
          setError: (err: string) => void,
      ) => {
          try {
              const ws = WaveSurfer.create({
                  container,
                  media: mediaEl,        // Sync playback with video element
                  waveColor: colors.wave,
                  progressColor: colors.progress,
                  cursorColor: 'transparent',
                  barWidth: 2,
                  barGap: 1,
                  height: 60,
                  normalize: true,
                  interact: false,
              });
              
              ws.on('error', (err: any) => {
                  console.error(`${label} WaveSurfer Error:`, err);
                  if (err.toString().includes('AbortError')) return;
                  if (err.toString().includes('Unable to decode')) {
                      setError("No audio track");
                  } else {
                      setError(err.toString());
                  }
              });
              
              // Pre-fetch audio as blob to bypass internal fetch issues
              try {
                  const response = await fetch(videoUrl);
                  if (!response.ok) throw new Error(`HTTP ${response.status}`);
                  const blob = await response.blob();
                  const blobUrl = URL.createObjectURL(blob);
                  blobUrlsToCleanup.push(blobUrl);
                  await ws.load(blobUrl);
                  console.log(`✅ ${label} waveform loaded via blob (${(blob.size / 1024 / 1024).toFixed(1)}MB)`);
              } catch (fetchErr: any) {
                  console.warn(`${label} blob fetch failed:`, fetchErr);
                  // Fallback: let WaveSurfer try to decode from the media element
                  // This may work for smaller files
              }
              
              return ws;
          } catch (e: any) {
              console.error(`${label} WaveSurfer Init Error:`, e);
              if (e.message && e.message.includes('Unable to decode')) {
                  setError("No audio track");
              } else {
                  setError(e.message || "Init Error");
              }
              return null;
          }
      };
      
      // Initialize both waveforms
      if (waveformRef.current && acceptanceVideoRef.current && acceptanceVideoUrl) {
          initWaveSurfer(
              waveformRef.current, acceptanceVideoRef.current, acceptanceVideoUrl,
              { wave: '#93c5fd', progress: '#2563eb' },
              'Acceptance', setWaveformError
          ).then(ws => { wavesurferRef.current = ws; });
      }
      
      if (emissionWaveformRef.current && emissionVideoRef.current && emissionVideoUrl) {
          // DELAY: Wait 500ms before starting second fetch to reduce concurrent pressure on single-threaded backend
          setTimeout(() => {
              if (emissionWaveformRef.current && emissionVideoRef.current && emissionVideoUrl) {
                  initWaveSurfer(
                      emissionWaveformRef.current, emissionVideoRef.current, emissionVideoUrl,
                      { wave: '#fca5a5', progress: '#dc2626' },
                      'Emission', setEmissionWaveformError
                  ).then(ws => { emissionWavesurferRef.current = ws; });
              }
          }, 500);
      }

      return () => {
          if (wavesurferRef.current) {
              wavesurferRef.current.destroy();
              wavesurferRef.current = null;
          }
          if (emissionWavesurferRef.current) {
              emissionWavesurferRef.current.destroy();
              emissionWavesurferRef.current = null;
          }
          // Cleanup blob URLs to free memory
          blobUrlsToCleanup.forEach(url => URL.revokeObjectURL(url));
      };
  }, [acceptanceVideoUrl, emissionVideoUrl, showResults]);
  const [showInspector, setShowInspector] = useState(false);
  const [inspectorInitialTimestamp, setInspectorInitialTimestamp] = useState<number | null>(null);

  
  // Video loading states
  const [acceptanceLoading, setAcceptanceLoading] = useState(true);
  const [emissionLoading, setEmissionLoading] = useState(true);
  const [acceptanceError, setAcceptanceError] = useState(false);
  const [emissionError, setEmissionError] = useState(false);



  // Load results from API
  useEffect(() => {
    const loadResults = async () => {
      if (job.status !== "completed") {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(
          `/api/v1/compare/${job.id}/results`
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
        const rawTime = acceptanceVideoRef.current.currentTime;
        const baseTime = Math.max(0, rawTime - acceptanceOffset);
        setCurrentTime(baseTime);
        
        // Sync Emission player only when playing to prevent fighting seekers
        if (emissionVideoRef.current && isPlaying) {
          const expectedEmiTime = baseTime + emissionOffset;
          if (Math.abs(emissionVideoRef.current.currentTime - expectedEmiTime) > 0.15) {
            emissionVideoRef.current.currentTime = expectedEmiTime;
          }
        }
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
  }, [acceptanceOffset, emissionOffset, isPlaying]);

  // Synchronized play/pause
  const togglePlayPause = () => {
    console.log("Toggle Play/Pause clicked! Is Playing:", isPlaying);
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];

    if (isPlaying) {
      videos.forEach((video) => video?.pause());
      setIsPlaying(false);
    } else {
      let readyCount = 0;
      const activeVideos: Array<{video: HTMLVideoElement, target: number}> = [];

      if (acceptanceVideoRef.current) {
         const target = currentTime + acceptanceOffset;
         if (Math.abs(acceptanceVideoRef.current.currentTime - target) > 0.1) {
            activeVideos.push({ video: acceptanceVideoRef.current, target });
         } else {
            readyCount++;
         }
      } else { readyCount++; }

      if (emissionVideoRef.current) {
         const target = currentTime + emissionOffset;
         if (Math.abs(emissionVideoRef.current.currentTime - target) > 0.1) {
            activeVideos.push({ video: emissionVideoRef.current, target });
         } else {
            readyCount++;
         }
      } else { readyCount++; }

      const startPlaying = () => {
        videos.forEach((video) => {
          if (video) {
            const playPromise = video.play();
            if (playPromise !== undefined) {
              playPromise.catch((err: any) => {
                if (err?.name !== 'AbortError') console.error('Play error:', err);
              });
            }
          }
        });
        setIsPlaying(true);
      };

      if (activeVideos.length > 0) {
        activeVideos.forEach(({ video, target }) => {
          const onSeeked = () => {
            video.removeEventListener('seeked', onSeeked);
            readyCount++;
            if (readyCount === 2) {
              startPlaying();
            }
          };
          video.addEventListener('seeked', onSeeked);
          video.currentTime = target;
        });
      } else {
        startPlaying();
      }
    }
  };

  const handleSeek = (time: number) => {
    if (acceptanceVideoRef.current) {
      acceptanceVideoRef.current.currentTime = time + acceptanceOffset;
    }
    if (emissionVideoRef.current) {
      emissionVideoRef.current.currentTime = time + emissionOffset;
    }
    setCurrentTime(time);
  };

  const jumpToDifference = (timestamp: number) => {
    handleSeek(timestamp);
    if (acceptanceVideoRef.current) acceptanceVideoRef.current.pause();
    if (emissionVideoRef.current) emissionVideoRef.current.pause();
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
    if (newVolume > 0) setPrevAcceptanceVol(newVolume);
    if (isMuted && newVolume > 0) setIsMuted(false);
  };

  const handleEmissionVolumeChange = (newVolume: number) => {
    setEmissionVolume(newVolume);
    if (newVolume > 0) setPrevEmissionVol(newVolume);
    if (isMuted && newVolume > 0) setIsMuted(false);
  };

  const toggleAcceptanceMute = () => {
    if (isMuted || acceptanceVolume === 0) {
      const restored = prevAcceptanceVol > 0 ? prevAcceptanceVol : 1;
      setAcceptanceVolume(restored);
      setIsMuted(false);
    } else {
      setPrevAcceptanceVol(acceptanceVolume);
      setAcceptanceVolume(0);
    }
  };

  const toggleEmissionMute = () => {
    if (isMuted || emissionVolume === 0) {
      const restored = prevEmissionVol > 0 ? prevEmissionVol : 1;
      setEmissionVolume(restored);
      setIsMuted(false);
    } else {
      setPrevEmissionVol(emissionVolume);
      setEmissionVolume(0);
    }
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

  const toggleShowResults = () => {
    setShowResults(!showResults);
  };

  // Process Dialog Timeline (Whisper)
  const dialogTimeline = useMemo(() => {
    const timelineData = results?.overall_result?.report_data?.audio?.speech_to_text?.timeline_data;
    if (!timelineData) return [];

    const segmentsA = timelineData.acceptance_segments || [];
    const segmentsB = timelineData.emission_segments || [];

    // Sort both by start time
    const sortedA = [...segmentsA].sort((a: any, b: any) => a.start - b.start);
    const sortedB = [...segmentsB].sort((a: any, b: any) => a.start - b.start);

    // Distribute emission text according to acceptance segments to avoid visual "missing" gaps
    // when Whisper chunks the same audio differently.
    
    // Reconstruct full emission text words
    const allEmiWords: string[] = [];
    sortedB.forEach((seg: any) => {
       const words = seg.text.trim().split(/\s+/);
       words.forEach((w: string) => {
           if (w.length > 0) allEmiWords.push(w);
       });
    });
    
    const events: Array<{ timestamp: number; acceptance?: string; emission?: string }> = [];
    
    // If there are no acceptance segments but there are emission segments
    if (sortedA.length === 0 && sortedB.length > 0) {
        sortedB.forEach((seg: any) => {
            events.push({ timestamp: seg.start, emission: seg.text });
        });
        return events;
    }

    let emiWordIdx = 0;
    
    sortedA.forEach((segA: any, index: number) => {
        const accWords = segA.text.trim().split(/\s+/).filter((w: string) => w.length > 0);
        let takeCount = accWords.length;
        
        // For the last segment, take all remaining emission words to not lose any text
        if (index === sortedA.length - 1) {
            takeCount = allEmiWords.length - emiWordIdx;
        }
        
        const segEmiWords = [];
        for (let i = 0; i < takeCount; i++) {
            if (emiWordIdx < allEmiWords.length) {
                segEmiWords.push(allEmiWords[emiWordIdx]);
                emiWordIdx++;
            }
        }
        
        events.push({
            timestamp: segA.start,
            acceptance: segA.text,
            emission: segEmiWords.length > 0 ? segEmiWords.join(" ") : "-"
        });
    });

    return events;
  }, [results]);

  const getOverallStatus = (similarity: number) => {
    if (similarity >= 0.95)
      return { label: "Excellent Match", color: "text-green-600", bg: "bg-green-100", animate: false };
    if (similarity >= 0.9)
      return { label: "Good Match", color: "text-blue-600", bg: "bg-blue-100", animate: false };
    if (similarity >= 0.8)
      return { label: "Fair Match", color: "text-yellow-600", bg: "bg-yellow-100", animate: false };
    if (similarity > 0)
      return { label: "Poor Match", color: "text-red-600", bg: "bg-red-100", animate: false };
    // similarity === 0: check job.status to distinguish "still running" vs "completed with no score"
    if (job.status === "completed")
      return { label: "Completed", color: "text-green-700", bg: "bg-green-100", animate: false };
    return { label: "Processing...", color: "text-gray-600", bg: "bg-gray-100", animate: true };
  };



  const isAcceptanceGif = useMemo(() => {
    const name = (job.acceptance_file?.original_name || job.acceptance_file?.filename || "").toLowerCase();
    return name.endsWith('.gif');
  }, [job.acceptance_file]);

  const isEmissionGif = useMemo(() => {
    const name = (job.emission_file?.original_name || job.emission_file?.filename || "").toLowerCase();
    return name.endsWith('.gif');
  }, [job.emission_file]);

  const status = getOverallStatus(overallScore);

  return (
    <div className="min-h-screen print:min-h-0 print:h-auto print:p-0 bg-slate-50 dark:bg-[#0d0e15] text-slate-900 dark:text-slate-100 p-6 transition-colors duration-200">
      <div className="max-w-7xl mx-auto">
        {/* Metryczka Raportu QA / Professional Report Summary Header */}
        <div className="mb-6 bg-white dark:bg-[#161824] rounded-2xl p-5 border border-slate-200 dark:border-white/10 shadow-md break-inside-avoid page-break-inside-avoid transition-colors">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-white/5 pb-3 mb-4 flex-wrap gap-2">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-cyan-400 rounded-xl flex items-center justify-center font-black text-lg border border-indigo-100 dark:border-indigo-900/40">
                📋
              </div>
              <div>
                <h1 className="text-lg font-black text-slate-900 dark:text-white uppercase tracking-wider">
                  {t.reportMetryczkaTitle || "METRYCZKA RAPORTU QA"}
                </h1>
                <p className="text-xs font-bold text-slate-500 dark:text-slate-400">
                  {job.job_name}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3 flex-wrap gap-2 print:hidden">
              <div
                className={`inline-flex items-center px-3.5 py-1.5 rounded-full text-xs font-black shadow-xs ${status.bg} ${status.color}`}
              >
                <div className={`w-2 h-2 bg-current rounded-full mr-2 ${status.animate ? "animate-pulse" : ""}`}></div>
                {status.label}
              </div>

              <button
                onClick={() => setShowResults(!showResults)}
                className="inline-flex items-center px-4 py-2 border border-slate-200 dark:border-white/10 rounded-xl text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 focus:outline-none transition-colors shadow-sm"
              >
                <ChartBarSquareIcon className="w-4 h-4 mr-2 text-indigo-600 dark:text-cyan-400" />
                {showResults ? (lang === "PL" ? "Ukryj Wyniki" : "Hide Results") : (lang === "PL" ? "Pokaż Wyniki" : "Show Results")}
              </button>
              
              {/* Inspect Button */}
              {differencesFound && (
                <button
                    onClick={() => {
                        setShowInspector(true);
                        setIsPlaying(false);
                    }}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-xl text-xs font-black text-white bg-gradient-to-r from-[#350F9C] to-[#4960E6] hover:opacity-90 shadow-md transition-all"
                >
                    <EyeIcon className="w-4 h-4 mr-2" />
                    {t.openInspector || "Inspect Differences"}
                </button>
              )}
            </div>
          </div>

          {/* Grid Metryczki */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            {/* Cradle ID */}
            <div className="bg-slate-50 dark:bg-[#12131c] p-3 rounded-xl border border-slate-200/60 dark:border-white/5">
              <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-0.5">{t.cradleId}</span>
              <span className="font-bold text-slate-900 dark:text-white font-mono text-sm">{job.cradle_id || "N/A"}</span>
            </div>

            {/* Client */}
            <div className="bg-slate-50 dark:bg-[#12131c] p-3 rounded-xl border border-slate-200/60 dark:border-white/5">
              <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-0.5">{t.client}</span>
              <span className="font-bold text-slate-900 dark:text-white text-sm truncate block">{job.client_name || "-"}</span>
            </div>

            {/* Analysis Date */}
            <div className="bg-slate-50 dark:bg-[#12131c] p-3 rounded-xl border border-slate-200/60 dark:border-white/5">
              <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-0.5">{t.dateCreated}</span>
              <span className="font-bold text-slate-900 dark:text-white text-xs">
                {new Date(job.created_at.endsWith('Z') ? job.created_at : job.created_at + 'Z').toLocaleString(lang === "PL" ? "pl-PL" : "en-US", { dateStyle: "medium", timeStyle: "short" })}
              </span>
            </div>

            {/* Commercial Duration */}
            <div className="bg-slate-50 dark:bg-[#12131c] p-3 rounded-xl border border-slate-200/60 dark:border-white/5">
              <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-0.5">{t.durationLabel}</span>
              <span className="font-bold text-slate-900 dark:text-white font-mono text-sm">{formatTime(displayDuration)}</span>
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
                acceptanceOffset,
                emissionOffset
            }}
            initialTimestamp={inspectorInitialTimestamp}
        />

        {/* Video Players - Side by Side (Touching seamlessly without gap, Sync DualPlayer style) */}
        <div id="video-player-section" className="grid grid-cols-1 lg:grid-cols-2 gap-0 mb-4">
          {/* Acceptance Video */}
          <div className="bg-white dark:bg-[#161824] rounded-2xl lg:rounded-r-none shadow-xl border border-slate-200 dark:border-white/10 lg:border-r-0 overflow-hidden transition-colors">
            <div className="px-4 py-2.5 border-b border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-[#12131c]">
              <div className="flex flex-col">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                    <h3 className="text-xs font-black text-brand-cobalt dark:text-white uppercase tracking-wider">
                      {t.acceptanceVideo}
                    </h3>
                  </div>
                  <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded-md border border-slate-300 dark:border-white/10">
                    ID: {job.acceptance_file_id}
                  </span>
                </div>
                <div className="flex items-center mt-1 space-x-2">
                  <p className="text-[11px] text-slate-600 dark:text-slate-300 font-semibold truncate min-w-0" title={job.acceptance_file?.original_name || job.acceptance_file?.filename || ''}>
                    {job.acceptance_file?.original_name || job.acceptance_file?.filename || 'Loading...'}
                  </p>
                  {job.acceptance_file?.width && job.acceptance_file?.height && (
                    <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {job.acceptance_file.width}x{job.acceptance_file.height}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="p-2">
              <div className="aspect-video bg-black rounded-xl overflow-hidden relative border border-slate-200 dark:border-white/5">
                {acceptanceLoading && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 z-10 backdrop-blur-sm">
                    <div className="animate-spin rounded-full h-10 w-10 border-3 border-indigo-500 border-t-transparent mb-3"></div>
                    <p className="text-white text-xs font-bold">Loading media...</p>
                  </div>
                )}
                {acceptanceError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 z-10 backdrop-blur-sm">
                    <p className="text-rose-400 text-xs font-bold">Failed to load media</p>
                    <button 
                      onClick={() => {
                        setAcceptanceError(false);
                        setAcceptanceLoading(true);
                        if (acceptanceVideoRef.current) {
                          acceptanceVideoRef.current.load();
                        }
                      }}
                      className="mt-2 px-3 py-1 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                )}
                {isAcceptanceGif ? (
                  <img
                    src={acceptanceVideoUrl}
                    alt="Acceptance GIF"
                    className="w-full h-full object-contain"
                    onLoad={() => setAcceptanceLoading(false)}
                    onError={() => {
                      setAcceptanceLoading(false);
                      setAcceptanceError(true);
                    }}
                  />
                ) : (
                  <video
                    ref={acceptanceVideoRef}
                    className="w-full h-full object-contain"
                    src={acceptanceVideoUrl}
                    crossOrigin="anonymous"
                    preload="auto"
                    onLoadedData={() => setAcceptanceLoading(false)}
                    onCanPlay={() => setAcceptanceLoading(false)}
                    onError={() => {
                      setAcceptanceLoading(false);
                      setAcceptanceError(true);
                    }}
                  />
                )}
              </div>
            </div>
            {/* Acceptance Volume Control */}
            <div className="px-3 py-1.5 bg-slate-50 dark:bg-[#12131c] border-t border-slate-200 dark:border-white/5 flex items-center space-x-2">
              <button
                type="button"
                onClick={toggleAcceptanceMute}
                className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                title={isMuted || acceptanceVolume === 0 ? "Włącz dźwięk akceptu" : "Wycisz dźwięk akceptu"}
              >
                {isMuted || acceptanceVolume === 0 ? (
                  <SpeakerXMarkIcon className="w-4 h-4 text-rose-500" />
                ) : (
                  <SpeakerWaveIcon className="w-4 h-4" />
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : acceptanceVolume}
                onChange={(e) => handleAcceptanceVolumeChange(Number(e.target.value))}
                className="w-24 h-1.5 bg-slate-300 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <span className="text-[11px] text-slate-500 dark:text-slate-400 w-8 tabular-nums font-bold">
                {Math.round((isMuted ? 0 : acceptanceVolume) * 100)}%
              </span>
            </div>
          </div>

          {/* Emission Video */}
          <div className="bg-white dark:bg-[#161824] rounded-2xl lg:rounded-l-none shadow-xl border border-slate-200 dark:border-white/10 overflow-hidden transition-colors">
            <div className="px-4 py-2.5 border-b border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-[#12131c]">
              <div className="flex flex-col">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                    <h3 className="text-xs font-black text-brand-cobalt dark:text-white uppercase tracking-wider">
                      {t.emissionVideo}
                    </h3>
                  </div>
                  <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded-md border border-slate-300 dark:border-white/10">
                    ID: {job.emission_file_id}
                  </span>
                </div>
                <div className="flex items-center space-x-2 mt-1">
                    <div className="flex items-center space-x-2 flex-grow min-w-0">
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 font-semibold truncate" title={job.emission_file?.original_name || job.emission_file?.filename || ''}>
                      {job.emission_file?.original_name || job.emission_file?.filename || 'Loading...'}
                      </p>
                      {job.emission_file?.width && job.emission_file?.height && (
                          <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {job.emission_file.width}x{job.emission_file.height}
                          </span>
                      )}
                    </div>
                    
                    {/* Heatmap Toggle */}
                    {results?.overall_result?.report_data?.video?.diff_frames && (
                        <button
                            onClick={() => setShowHeatmap(!showHeatmap)}
                            className={`flex items-center space-x-1 px-2.5 py-0.5 rounded-lg text-xs font-bold transition-all ${
                                showHeatmap 
                                ? 'bg-indigo-600 text-white shadow-md' 
                                : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700'
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
            <div className="p-2">
              <div className="aspect-video bg-black rounded-xl overflow-hidden relative border border-slate-200 dark:border-white/5">
                {emissionLoading && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 z-10 backdrop-blur-sm">
                    <div className="animate-spin rounded-full h-10 w-10 border-3 border-indigo-500 border-t-transparent mb-3"></div>
                    <p className="text-white text-xs font-bold">Loading video...</p>
                  </div>
                )}
                {emissionError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 z-10 backdrop-blur-sm">
                    <p className="text-rose-400 text-xs font-bold">Failed to load video</p>
                    <button 
                      onClick={() => {
                        setEmissionError(false);
                        setEmissionLoading(true);
                        if (emissionVideoRef.current) {
                          emissionVideoRef.current.load();
                        }
                      }}
                      className="mt-2 px-3 py-1 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                )}
                {isEmissionGif ? (
                  <img
                    src={emissionVideoUrl}
                    alt="Emission GIF"
                    className="w-full h-full object-contain"
                    onLoad={() => setEmissionLoading(false)}
                    onError={() => {
                      setEmissionLoading(false);
                      setEmissionError(true);
                    }}
                  />
                ) : (
                  <video
                    ref={emissionVideoRef}
                    className="w-full h-full object-contain"
                    src={emissionVideoUrl}
                    crossOrigin="anonymous"
                    preload="auto"
                    onLoadedData={() => setEmissionLoading(false)}
                    onCanPlay={() => setEmissionLoading(false)}
                    onError={() => {
                      setEmissionLoading(false);
                      setEmissionError(true);
                    }}
                  />
                )}
                
                {/* Heatmap Overlay */}
                {showHeatmap && currentDiffImage && (
                    <div className="absolute inset-0 z-20 pointer-events-none opacity-80 mix-blend-screen">
                        <img 
                            src={`${currentDiffImage}`} 
                            alt="Difference Heatmap" 
                            className="w-full h-full object-contain"
                        />
                        <div className="absolute top-2 right-2 bg-rose-600 text-white text-[10px] px-1.5 py-0.5 rounded shadow-sm opacity-90 font-black uppercase tracking-wider">
                            DIFF
                        </div>
                    </div>
                )}

              </div>
            </div>
            {/* Emission Volume Control */}
            <div className="px-3 py-1.5 bg-slate-50 dark:bg-[#12131c] border-t border-slate-200 dark:border-white/5 flex items-center space-x-2">
              <button
                type="button"
                onClick={toggleEmissionMute}
                className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                title={isMuted || emissionVolume === 0 ? "Włącz dźwięk emisji" : "Wycisz dźwięk emisji"}
              >
                {isMuted || emissionVolume === 0 ? (
                  <SpeakerXMarkIcon className="w-4 h-4 text-rose-500" />
                ) : (
                  <SpeakerWaveIcon className="w-4 h-4" />
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={isMuted ? 0 : emissionVolume}
                onChange={(e) => handleEmissionVolumeChange(Number(e.target.value))}
                className="w-24 h-1.5 bg-slate-300 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <span className="text-[11px] text-slate-500 dark:text-slate-400 w-8 tabular-nums font-bold">
                {Math.round((isMuted ? 0 : emissionVolume) * 100)}%
              </span>
            </div>
          </div>
        </div>

        {/* Synchronized Video Controls - Neutral Card Container without blue apla, with Blue Tracks */}
        <div className="bg-white dark:bg-[#161824] text-slate-900 dark:text-white rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 p-4 mb-8 transition-colors">
          <div className="flex items-center justify-between">
            <div className="flex items-start space-x-4 flex-grow">
              <button
                onClick={togglePlayPause}
                className="w-11 h-11 flex items-center justify-center bg-blue-600 dark:bg-indigo-600 text-white hover:scale-105 transition-transform rounded-full shadow-md flex-shrink-0 relative z-10 font-black"
              >
                {isPlaying ? (
                  <PauseIcon className="w-5 h-5" />
                ) : (
                  <PlayIcon className="w-6 h-6 ml-1" />
                )}
              </button>

              <div className="flex items-center space-x-2 flex-grow mx-4">
                <div className="flex-grow flex flex-col">
                  <div className="h-12 flex items-center space-x-3">
                    <span className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300 w-12 text-right">
                      {formatTime(currentTime)}
                    </span>
                    <input
                      type="range"
                      min="0"
                      max={displayDuration || 100}
                      value={currentTime}
                      onChange={(e) => handleSeek(Number(e.target.value))}
                      className="flex-grow h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:accent-cyan-400"
                    />
                    <span className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300 w-12">
                      {formatTime(displayDuration)}
                    </span>
                  </div>
                  
                  {/* Difference Tracks Container */}
                  <div className="mt-3 space-y-2.5 w-full">
                    
                    {/* 1. VIDEO Differences Track (RED PASKI) */}
                    <div className="flex items-center space-x-3 w-full">
                      <span className="text-[10px] font-bold text-red-600 dark:text-rose-400 uppercase w-12 text-right flex-shrink-0">
                        Video
                      </span>
                      <div className="relative h-4 flex-grow bg-slate-100 dark:bg-[#12131c] rounded-lg border border-slate-200 dark:border-white/10 flex items-center overflow-hidden">
                        {displayDuration > 0 && differences.map((diff, index) => {
                          const position = (diff.timestamp_seconds / displayDuration) * 100;
                          return (
                            <div
                              key={`video-${index}`}
                              onClick={() => {
                                jumpToDifference(diff.timestamp_seconds);
                                setInspectorInitialTimestamp(diff.timestamp_seconds);
                                setShowInspector(true);
                              }}
                              className="absolute bg-red-600 dark:bg-rose-500 hover:opacity-80 cursor-pointer z-10"
                              style={{ 
                                  left: `${position}%`, 
                                  width: '2.5px', 
                                  height: '100%' 
                              }}
                              title={`🎬 Video Diff: ${formatTime(diff.timestamp_seconds)}`}
                            />
                          );
                        })}
                      </div>
                      <span className="w-12 flex-shrink-0"></span>
                    </div>

                    {/* 2. AUDIO Differences Track (INDIGO PASKI) */}
                    <div className="flex items-center space-x-3 w-full">
                      <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase w-12 text-right flex-shrink-0">
                        Audio
                      </span>
                      <div className="relative h-4 flex-grow bg-slate-100 dark:bg-[#12131c] rounded-lg border border-slate-200 dark:border-white/10 flex items-center overflow-hidden">
                        {audioDiffSegments.map((seg: any, index: number) => {
                           const timeStr = seg.time_a !== "(missing)" ? seg.time_a : seg.time_b;
                           const time = parseFloat(timeStr.replace('s', ''));
                           
                           if (isNaN(time) || displayDuration <= 0) return null;
                           
                           const position = (time / displayDuration) * 100;
                           
                           return (
                             <div
                               key={`audio-${index}`}
                               onClick={() => {
                                 handleSeek(time);
                               }}
                               className="absolute bg-indigo-500 dark:bg-indigo-400 hover:opacity-80 cursor-pointer z-10 rounded-full"
                               style={{ 
                                   left: `${position}%`, 
                                   width: '6px', 
                                   height: '6px',
                                   transform: 'translateX(-50%)'
                               }}
                               title={`🎤 Audio Diff: ${seg.text_a || 'Missing'} vs ${seg.text_b || 'Missing'}`}
                             />
                           );
                        })}
                      </div>
                      <span className="w-12 flex-shrink-0"></span>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
              <button
                onClick={toggleMute}
                className={`p-2.5 rounded-xl transition-all border ${isMuted ? 'bg-rose-500 text-white font-bold border-rose-600' : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border-slate-200 dark:border-white/10'}`}
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
          <div className="flex items-center justify-center gap-6 text-xs text-slate-500 dark:text-slate-400 mt-4 pt-3 border-t border-slate-100 dark:border-white/5">
            <div className="flex items-center font-bold">
              <div className="w-2.5 h-2.5 bg-red-600 dark:bg-rose-500 rounded-full mr-2 shadow-sm"></div>
              Video Differences
            </div>

            <div className="flex items-center font-bold">
              <div className="w-2.5 h-2.5 bg-indigo-500 dark:bg-indigo-400 rounded-full mr-2 shadow-sm"></div>
              Audio Differences
            </div>
          </div>
        </div>

        {/* Results Panel */}
        {showResults && (
          <div className="bg-white dark:bg-[#161824] rounded-2xl shadow-xl border border-slate-200 dark:border-white/10 p-6 transition-colors">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div className="flex items-center">
                <DocumentChartBarIcon className="w-6 h-6 text-indigo-600 dark:text-cyan-400 mr-3" />
                <h2 className="text-xl font-black text-slate-900 dark:text-white">
                  Comparison Results
                </h2>
                {loading && <span className="ml-2 text-xs font-bold text-slate-400">(Loading...)</span>}
              </div>
              
              <div className="flex items-center space-x-3">
                 {/* Print Button - visible on screen, hidden on print */}
                 <button 
                    onClick={() => {
                      const oldTitle = document.title;
                      document.title = job.cradle_id ? `${job.cradle_id}` : job.job_name || 'report';
                      setTimeout(() => {
                        window.print();
                        document.title = oldTitle;
                      }, 50);
                    }} 
                    className="flex items-center space-x-1 px-3.5 py-1.5 bg-emerald-500 border border-transparent text-white rounded-xl hover:bg-emerald-600 text-xs font-bold print:hidden shadow-sm transition-colors"
                 >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
                    </svg>
                    <span>Export PDF</span>
                 </button>
              </div>

              {/* Re-analyze dropdown with current level indicator */}
              <div className="flex items-center gap-2 print:hidden">
                <span className="text-xs font-bold text-slate-500 dark:text-slate-400">
                  Current: <span className="font-black capitalize text-slate-800 dark:text-slate-200">{job.comparison_type === "automation" ? "Automation" : (job.sensitivity_level || "medium")}</span>
                </span>
                <span className="text-slate-300 dark:text-slate-700">|</span>
                <span className="text-xs font-bold text-slate-500 dark:text-slate-400">Re-analyze:</span>
                
                {/* Manual Levels */}
                {(["high", "automation", "vo_transcript"] as const).map((level) => {
                  const levelStr = level as string;
                  const isCurrent = ((job.sensitivity_level as string) || "medium") === levelStr && 
                                   (levelStr === "automation" ? job.comparison_type === "automation" : levelStr === "vo_transcript" ? job.comparison_type === "vo_transcript" : job.comparison_type !== "automation" && job.comparison_type !== "vo_transcript");
                  
                  return (
                    <button
                      key={levelStr}
                      disabled={reanalyzing || (isCurrent && levelStr !== "automation" && levelStr !== "vo_transcript")}
                      onClick={async () => {
                        setReanalyzing(true);
                        try {
                          if (levelStr === "automation") {
                              localStorage.setItem("cradle-auto-video-compare", "true");
                              console.log("[VideoComparison] 🤖 Arming Extension for Auto Hand-off...");
                          }

                          const formData = new FormData();
                          formData.append("sensitivity_level", levelStr === "vo_transcript" ? "automation" : levelStr);
                          formData.append("comparison_type", levelStr === "automation" ? "automation" : levelStr === "vo_transcript" ? "vo_transcript" : "full");
                          
                          const response = await fetch(
                            `/api/v1/compare/${job.id}/reanalyze`,
                            { method: "POST", body: formData }
                          );

                          if (response.ok) {
                            const data = await response.json();
                            if (data.new_job_id) {
                                window.location.href = `/compare/${data.new_job_id}`;
                            } else {
                                window.location.reload();
                            }
                          } else {
                            const errText = await response.text();
                            alert("Failed: " + errText);
                            localStorage.removeItem("cradle-auto-video-compare");
                          }
                        } catch (err) {
                          console.error(err);
                          alert("Error starting re-analysis");
                          localStorage.removeItem("cradle-auto-video-compare");
                        } finally {
                          setReanalyzing(false);
                        }
                      }}
                      className={`px-3 py-1.5 text-xs rounded-xl transition-all font-black ${
                        levelStr === "high" ? "bg-rose-100 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 hover:bg-rose-200" :
                        levelStr === "vo_transcript" ? "bg-purple-600 text-white hover:bg-purple-700 shadow-md" :
                        "bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white hover:opacity-90 shadow-md"
                      } ${isCurrent && levelStr !== "automation" && levelStr !== "vo_transcript" ? "ring-2 ring-offset-1 ring-indigo-500" : ""} ${
                        reanalyzing || (isCurrent && levelStr !== "automation" && levelStr !== "vo_transcript") ? "opacity-50 cursor-not-allowed" : ""
                      }`}
                    >
                      {levelStr === "automation" ? "🤖 Run Auto-Compare" : levelStr === "vo_transcript" ? "🎙️ Run VO Transcript" : levelStr.charAt(0).toUpperCase() + levelStr.slice(1)}
                      {isCurrent && " ✓"}
                    </button>
                  );
                })}
              </div>
            </div>

            {results ? (
              <>
                {/* Similarity Scores - Minimalist & Unified */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                  {/* Overall Similarity */}
                  <div className="text-center p-5 bg-slate-50 dark:bg-[#12131c] border border-slate-200 dark:border-white/10 rounded-2xl">
                    <div className="text-3xl font-black text-slate-900 dark:text-white mb-1">
                      {Math.round((overallScore || 0) * 100)}%
                    </div>
                    <h3 className="text-xs font-black text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Overall Similarity
                    </h3>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mt-0.5">Combined analysis</p>
                  </div>

                  {/* Video Similarity */}
                  <div className="text-center p-5 bg-slate-50 dark:bg-[#12131c] border border-slate-200 dark:border-white/10 rounded-2xl">
                    <div className="text-3xl font-black text-slate-900 dark:text-white mb-1">
                      {Math.round((videoSimilarity || 0) * 100)}%
                    </div>
                    <h3 className="text-xs font-black text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Video Similarity
                    </h3>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mt-0.5">
                      {videoDifferences} / {totalFrames} frames differ
                    </p>
                  </div>

                  {/* Audio Similarity */}
                  <div className="text-center p-5 bg-slate-50 dark:bg-[#12131c] border border-slate-200 dark:border-white/10 rounded-2xl">
                    <div className="text-3xl font-black text-slate-900 dark:text-white mb-1">
                      {audioSimilarity != null ? `${Math.round(audioSimilarity * 100)}%` : "N/A"}
                    </div>
                    <h3 className="text-xs font-black text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      {t.audioDifferences || "Audio Similarity"}
                    </h3>
                    <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mt-0.5">
                      {audioSimilarity != null ? "Spectral analysis" : (lang === "PL" ? "Brak ścieżki dźwiękowej" : "No audio track")}
                    </p>
                  </div>
                </div>


                {/* Audio Results Section */}
                {results.overall_result?.report_data?.audio?.loudness && (() => {
                  const audio = results.overall_result.report_data.audio;
                  const loudness = audio.loudness;
                  const similarity = audio.similarity;
                  
                  return (
                    <div id="audio-results-section" className="mb-8 border border-slate-200 dark:border-white/10 rounded-2xl overflow-hidden">
                      {/* Header */}
                      <div className="flex items-center justify-between p-4 bg-slate-100 dark:bg-[#12131c] border-b border-slate-200 dark:border-white/10">
                        <h3 className="text-xs font-black text-slate-900 dark:text-white flex items-center uppercase tracking-wider">
                          🔊 Audio Comparison
                          {detectedLanguage && (
                              <span className="ml-2 px-2 py-0.5 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[10px] rounded border border-slate-300 dark:border-white/10 font-mono" title="Detected Language">
                                  {detectedLanguage}
                              </span>
                          )}
                          {audio.has_loudness_differences ? (
                            <span className="ml-2 px-2.5 py-0.5 bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-[11px] rounded-md font-bold border border-rose-200 dark:border-rose-900/40">
                              Loudness Differences
                            </span>
                          ) : (
                            <span className="ml-2 px-2.5 py-0.5 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-[11px] rounded-md font-bold border border-emerald-200 dark:border-emerald-900/40">
                              ✓ Loudness match
                            </span>
                          )}
                        </h3>
                        {similarity && (
                          <span className="text-lg font-black text-indigo-600 dark:text-cyan-400">
                            {Math.round((similarity.overall_audio_similarity || 0) * 100)}% match
                          </span>
                        )}
                      </div>
                      
                      {/* Two Panel View - LUFS */}
                      <div className="grid grid-cols-2 gap-0 border-b border-slate-200 dark:border-white/10">
                        {/* Acceptance LUFS */}
                        <div className="border-r border-slate-200 dark:border-white/10">
                          <div className="bg-slate-200 dark:bg-slate-800 text-slate-900 dark:text-white px-4 py-2 font-black text-xs text-center uppercase tracking-wider">
                            Acceptance LUFS
                          </div>
                          <div className="p-4 bg-slate-50 dark:bg-slate-900/60">
                            {loudness?.acceptance ? (
                              <>
                                <div className="text-center mb-3">
                                  <span className="text-3xl font-black text-slate-900 dark:text-white">
                                    {typeof loudness.acceptance.integrated_lufs === 'number' ? loudness.acceptance.integrated_lufs : 'N/A'}
                                  </span>
                                  <span className="text-xs font-bold text-slate-500 dark:text-slate-400 ml-1">LUFS</span>
                                </div>
                                <div className="text-xs font-bold text-slate-600 dark:text-slate-300 space-y-1">
                                  <div className="flex justify-between">
                                    <span>True Peak:</span>
                                    <span className="font-mono">{loudness.acceptance.true_peak_db} dB</span>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <p className="text-slate-400 text-xs italic">Brak danych</p>
                            )}
                          </div>
                        </div>
                        
                        {/* Emission LUFS */}
                        <div>
                          <div className="bg-slate-200 dark:bg-slate-800 text-slate-900 dark:text-white px-4 py-2 font-black text-xs text-center uppercase tracking-wider">
                            Emission LUFS
                          </div>
                          <div className="p-4 bg-slate-50 dark:bg-slate-900/60">
                            {loudness?.emission ? (
                              <>
                                <div className="text-center mb-3">
                                  <span className="text-3xl font-black text-slate-900 dark:text-white">
                                    {typeof loudness.emission.integrated_lufs === 'number' ? loudness.emission.integrated_lufs : 'N/A'}
                                  </span>
                                  <span className="text-xs font-bold text-slate-500 dark:text-slate-400 ml-1">LUFS</span>
                                </div>
                                <div className="text-xs font-bold text-slate-600 dark:text-slate-300 space-y-1">
                                  <div className="flex justify-between">
                                    <span>True Peak:</span>
                                    <span className="font-mono">{loudness.emission.true_peak_db} dB</span>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <p className="text-slate-400 text-xs italic">Brak danych</p>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {/* Comparison Summary */}
                      {loudness?.comparison && (
                        <div className="p-4 bg-slate-100 dark:bg-slate-800/60">
                          <div className="grid grid-cols-2 gap-4 text-center">
                            <div className={`p-3 rounded-xl border ${loudness.comparison.is_lufs_match ? 'bg-emerald-100/60 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-rose-100/60 dark:bg-rose-950/40 border-rose-300 dark:border-rose-900/40 text-rose-800 dark:text-rose-300'}`}>
                              <div className="text-xs font-bold opacity-80">LUFS Difference</div>
                              <div className="text-sm font-mono font-black mt-1">
                                {typeof loudness.comparison.lufs_difference === 'number' ? `${loudness.comparison.lufs_difference > 0 ? '+' : ''}${loudness.comparison.lufs_difference.toFixed(1)} LU` : 'N/A'}
                                <span className="ml-2 text-[10px] font-bold opacity-80">
                                  ({loudness.comparison.is_lufs_match ? '✓ Within tolerance ±1 LU' : '⚠️ Out of tolerance'})
                                </span>
                              </div>
                            </div>
                            <div className={`p-3 rounded-xl border ${loudness.comparison.is_peak_match ? 'bg-emerald-100/60 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-rose-100/60 dark:bg-rose-950/40 border-rose-300 dark:border-rose-900/40 text-rose-800 dark:text-rose-300'}`}>
                              <div className="text-xs font-bold opacity-80">Peak Difference</div>
                              <div className="text-sm font-mono font-black mt-1">
                                {typeof loudness.comparison.peak_difference_db === 'number' ? `${loudness.comparison.peak_difference_db > 0 ? '+' : ''}${loudness.comparison.peak_difference_db.toFixed(1)} dB` : 'N/A'}
                                <span className="ml-2 text-[10px] font-bold opacity-80">
                                  ({loudness.comparison.is_peak_match ? '✓ Within tolerance ±1 dB' : '⚠️ Out of tolerance'})
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Audio Waveforms (Stacked) */}
                      <div className="mt-6 mb-8">
                        <h4 className="text-xs font-black text-slate-700 dark:text-slate-200 uppercase tracking-wider mb-3 flex items-center">
                          <span className="bg-slate-100 dark:bg-slate-800 p-1.5 rounded-lg mr-2">🌊</span>
                          Audio Waveform Comparison
                        </h4>
                        <div className="bg-slate-50 dark:bg-slate-900/60 rounded-2xl border border-slate-200 dark:border-white/10 p-4 space-y-4">
                          
                          {/* Acceptance Waveform */}
                          <div className="relative">
                            <div className="flex justify-between items-center mb-1">
                              <span className="text-[11px] font-black text-indigo-600 dark:text-cyan-400 uppercase tracking-wider">Acceptance Audio</span>
                              {waveformError && (
                                <span className={`text-[10px] font-bold px-2 rounded border ${waveformError === 'No audio track' ? 'text-slate-500 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-white/10' : 'text-rose-500 bg-white dark:bg-slate-900 border-rose-200'}`}>
                                  {waveformError === 'No audio track' ? waveformError : `Error: ${waveformError}`}
                                </span>
                              )}
                            </div>
                            <div className="h-[60px] w-full bg-white dark:bg-[#12131c] rounded-xl border border-indigo-100 dark:border-indigo-900/40 relative overflow-hidden">
                              <div ref={waveformRef} className="absolute inset-0 w-full h-full" />
                              {/* Central Line */}
                              <div className="absolute top-1/2 left-0 right-0 h-px bg-indigo-100 dark:bg-indigo-900/40 z-0"></div>
                            </div>
                          </div>

                          {/* Emission Waveform */}
                          <div className="relative">
                            <div className="flex justify-between items-center mb-1">
                              <span className="text-[11px] font-black text-rose-600 dark:text-rose-400 uppercase tracking-wider">Emission Audio</span>
                              {emissionWaveformError && (
                                <span className={`text-[10px] font-bold px-2 rounded border ${emissionWaveformError === 'No audio track' ? 'text-slate-500 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-white/10' : 'text-rose-500 bg-white dark:bg-slate-900 border-rose-200'}`}>
                                  {emissionWaveformError === 'No audio track' ? emissionWaveformError : `Error: ${emissionWaveformError}`}
                                </span>
                              )}
                            </div>
                            <div className="h-[60px] w-full bg-white dark:bg-[#12131c] rounded-xl border border-rose-100 dark:border-rose-900/40 relative overflow-hidden">
                              <div ref={emissionWaveformRef} className="absolute inset-0 w-full h-full" />
                              {/* Central Line */}
                              <div className="absolute top-1/2 left-0 right-0 h-px bg-rose-100 dark:bg-rose-900/40 z-0"></div>
                            </div>
                          </div>

                        </div>
                      </div>
                      
                      {/* Voiceover Comparison (if both have vocals) */}
                      {audio.voiceover && (
                        <div className={`mt-4 p-4 rounded-2xl border ${audio.voiceover.is_same_voice ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900/40' : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900/40'}`}>
                          <h4 className="text-xs font-black text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-3">
                            🎤 Voiceover Comparison
                          </h4>
                          <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 mb-1">Voice Similarity</div>
                              <div className={`text-2xl font-black ${audio.voiceover.is_same_voice ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                                {Math.round(audio.voiceover.voice_similarity * 100)}%
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 mb-1">Same Voice?</div>
                              <div className={`text-lg font-black ${audio.voiceover.is_same_voice ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                                {audio.voiceover.is_same_voice ? '✓ TAK' : '⚠️ NIE'}
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 mb-1">Sync Status</div>
                              <div className={`text-lg font-black ${audio.voiceover.timing?.is_synced ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                                {audio.voiceover.timing?.is_synced ? '✓ Synced' : `${audio.voiceover.timing?.average_offset_seconds?.toFixed(2)}s offset`}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Transcript Comparison (HIGH sensitivity only) */}
                      {audio.speech_to_text && (
                        <div className="mt-4 p-4 bg-slate-50 dark:bg-slate-900/60 rounded-2xl border border-slate-200 dark:border-white/10">
                          <h4 className="flex items-center text-xs font-black text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-3">
                            📝 Transcript Comparison (Whisper)
                            {audio.speech_to_text.detected_language && (
                                <span className="ml-2 px-2 py-0.5 text-[10px] rounded-full bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-300 uppercase border border-indigo-200 dark:border-indigo-900/40 font-mono" title="Detected Language">
                                    {audio.speech_to_text.detected_language}
                                </span>
                            )}
                            <span className={`ml-2 px-2 py-0.5 text-[10px] rounded-full font-black ${audio.speech_to_text.is_text_match ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300'}`}>
                              {Math.round(audio.speech_to_text.text_similarity * 100)}% match
                            </span>
                          </h4>
                          
                          <div className="space-y-4">
                            {/* Comparison View */}
                            {audio.speech_to_text.comparison && audio.speech_to_text.comparison.total_differences > 0 ? (
                              <div className="bg-white dark:bg-[#12131c] p-3 rounded-xl border border-slate-200 dark:border-white/10 max-h-40 overflow-y-auto">
                                <div className="text-xs text-slate-500 dark:text-slate-400 mb-2 font-bold">Word Differences Detected:</div>
                                {audio.speech_to_text.comparison.word_differences.map((diff, idx) => (
                                  <div key={idx} className="mb-2 text-xs pl-2 border-l-2 border-rose-300">
                                    <div className="flex gap-2">
                                      <span className="text-slate-400 w-16 text-[10px] font-bold uppercase">{diff.type}</span>
                                      <div className="flex-1 font-mono text-xs">
                                        {diff.acceptance && (
                                          <div className="text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-1 rounded inline-block mr-1">
                                            {diff.acceptance}
                                          </div>
                                        )}
                                        {diff.emission && (
                                          <div className="text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/60 px-1 rounded inline-block decoration-slice">
                                            {diff.emission}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="bg-emerald-50 dark:bg-emerald-950/40 p-3 rounded-xl text-emerald-700 dark:text-emerald-300 text-xs font-bold flex items-center">
                                <span className="mr-2">✓</span> No text differences found
                              </div>
                            )}

                            {/* Dialog Timeline (Whisper) - Side by Side */}
                            {dialogTimeline.length > 0 ? (
                              <div className="mt-4">
                                <h4 className="text-xs font-black text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-2">Detected Dialog Timeline</h4>
                                <div className="max-h-96 overflow-y-auto border border-slate-200 dark:border-white/10 rounded-xl">
                                  <table className="min-w-full divide-y divide-slate-100 dark:divide-white/5 text-xs table-fixed">
                                    <thead className="bg-slate-100 dark:bg-slate-800/80 sticky top-0 z-10 shadow-sm">
                                      <tr>
                                        <th scope="col" className="px-3 py-2 text-left font-black text-slate-500 dark:text-slate-400 uppercase tracking-wider w-24 text-[10px]">Time</th>
                                        <th scope="col" className="px-3 py-2 text-left font-black text-indigo-600 dark:text-cyan-400 uppercase tracking-wider w-1/2 text-[10px]">
                                          Acceptance
                                        </th>
                                        <th scope="col" className="px-3 py-2 text-left font-black text-indigo-600 dark:text-indigo-400 uppercase tracking-wider w-1/2 text-[10px]">
                                          Emission
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody className="bg-white dark:bg-[#161824] divide-y divide-slate-100 dark:divide-white/5">
                                      {dialogTimeline.map((item, idx) => {
                                        const normA = (item.acceptance || "").toLowerCase().replace(/[.,?!:;\-"']/g, "").replace(/\s+/g, " ").trim();
                                        const normB = (item.emission || "").toLowerCase().replace(/[.,?!:;\-"']/g, "").replace(/\s+/g, " ").trim();
                                        const isMismatch = Boolean(item.acceptance && item.emission && normA !== normB);

                                        return (
                                          <tr 
                                            key={idx} 
                                            className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition-colors ${isMismatch ? 'bg-amber-50/60 dark:bg-amber-950/20' : ''}`}
                                            onClick={() => jumpToDifference(item.timestamp)}
                                          >
                                            <td className="px-3 py-2 whitespace-nowrap font-mono text-xs font-bold text-slate-500 dark:text-slate-400 align-top">
                                              {formatTime(item.timestamp)}
                                            </td>
                                            <td className="px-3 py-2 text-slate-900 dark:text-slate-200 break-words align-top border-r border-slate-100 dark:border-white/5">
                                              {item.acceptance ? (
                                                <div className="bg-indigo-50/60 dark:bg-indigo-950/40 p-1.5 rounded-lg text-xs font-medium">
                                                  {item.acceptance}
                                                </div>
                                              ) : (
                                                <span className="text-slate-400 italic text-xs">-</span>
                                              )}
                                            </td>
                                            <td className="px-3 py-2 text-slate-900 dark:text-slate-200 break-words align-top">
                                              {item.emission ? (
                                                <div className={`p-1.5 rounded-lg text-xs font-medium ${isMismatch ? 'bg-rose-100/80 dark:bg-rose-950/60 text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-900/50' : 'bg-indigo-50/60 dark:bg-indigo-950/40'}`}>
                                                  {item.emission}
                                                </div>
                                              ) : (
                                                <span className="text-slate-400 italic text-xs">-</span>
                                              )}
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            ) : (
                              <div className="text-center p-4 bg-slate-50 dark:bg-slate-900/40 rounded-xl text-slate-400 text-xs font-bold italic">
                                No dialog timeline available.
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* ======================== INSPECT DIFFERENCES REPORT SECTION ======================== */}
                {differencesFound && (
                  <div className="hidden print:block mt-8 pt-6 border-t border-slate-200 dark:border-white/10 break-inside-avoid page-break-inside-avoid">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-2">
                        <EyeIcon className="w-5 h-5 text-red-500" />
                        <h3 className="text-lg font-black text-slate-900 dark:text-white">
                          {t.frameAnalysis || "Frame Differences Analysis (Inspect Differences)"}
                        </h3>
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800/40">
                          {differences.length > 0 ? `${differences.length} diffs` : `${videoDifferences} frames`}
                        </span>
                      </div>
                      
                      <button
                        onClick={() => setShowInspector(true)}
                        className="px-3.5 py-1.5 bg-gradient-to-r from-[#350F9C] to-[#4960E6] text-white rounded-xl text-xs font-bold hover:opacity-90 transition-all shadow-sm print:hidden flex items-center space-x-1.5"
                      >
                        <span>{t.openInspector || "Open Interactive Inspector"}</span>
                        <ChevronRightIcon className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {(() => {
                        const sortedDiffs = [...differences].sort((a, b) => a.timestamp_seconds - b.timestamp_seconds);
                        const diffFrames = results?.overall_result?.report_data?.video?.diff_frames || {};

                        return sortedDiffs.map((diff, index) => {
                          const time = diff.timestamp_seconds;
                          const timeKeyInt = Math.floor(time).toString();
                          const timeKeyFloat = time.toFixed(1);
                          let diffImg = diffFrames[timeKeyInt] || diffFrames[timeKeyFloat];
                          
                          if (!diffImg && Object.keys(diffFrames).length > 0) {
                            const keys = Object.keys(diffFrames);
                            const closestKey = keys.reduce((prev, curr) => 
                              Math.abs(Number(curr) - time) < Math.abs(Number(prev) - time) ? curr : prev
                            );
                            if (Math.abs(Number(closestKey) - time) < 1.0) {
                              diffImg = diffFrames[closestKey];
                            }
                          }

                          return (
                            <div 
                              key={`diff-report-card-${index}`}
                              className="bg-slate-50 dark:bg-[#12131c] rounded-xl p-3 border border-slate-200 dark:border-white/10 flex flex-col justify-between break-inside-avoid page-break-inside-avoid shadow-sm"
                            >
                              <div>
                                <div className="flex items-center justify-between mb-2">
                                  <span className="px-2 py-0.5 bg-red-100 dark:bg-rose-950/60 text-red-700 dark:text-rose-300 font-mono font-bold text-xs rounded-md border border-red-200 dark:border-rose-800/30">
                                    ⏱ {formatTime(time)}
                                  </span>
                                  <span className="text-[10px] font-extrabold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                                    {diff.difference_type || 'Visual Difference'}
                                  </span>
                                </div>

                                {diffImg ? (
                                  <div className="aspect-video bg-black rounded-lg overflow-hidden border border-slate-200 dark:border-white/10 mb-2.5 relative">
                                    <img 
                                      src={diffImg} 
                                      alt={`Difference at ${formatTime(time)}`} 
                                      className="w-full h-full object-contain"
                                    />
                                    <div className="absolute bottom-1 right-1 bg-black/75 backdrop-blur-xs px-1.5 py-0.5 rounded text-[9px] font-bold text-white uppercase border border-white/10">
                                      Heatmap
                                    </div>
                                  </div>
                                ) : (
                                  <div className="aspect-video bg-slate-200/60 dark:bg-slate-800/60 rounded-lg flex items-center justify-center mb-2.5 text-slate-400 text-xs font-semibold italic border border-slate-300 dark:border-white/5">
                                    Frame diff detected
                                  </div>
                                )}
                              </div>

                              <div className="flex items-center justify-between text-[11px] font-bold text-slate-600 dark:text-slate-300 pt-1 border-t border-slate-200/60 dark:border-white/5">
                                <span>Confidence: <strong className="text-slate-900 dark:text-white">{diff.confidence ? (diff.confidence > 1 ? `${diff.confidence}%` : `${(diff.confidence * 100).toFixed(1)}%`) : 'N/A'}</strong></span>
                                <button
                                  onClick={() => {
                                    jumpToDifference(time);
                                    setInspectorInitialTimestamp(time);
                                    setShowInspector(true);
                                  }}
                                  className="text-xs font-bold text-indigo-600 dark:text-cyan-400 hover:underline print:hidden flex items-center space-x-0.5"
                                >
                                  <span>{t.inspect || "Inspect"}</span>
                                  <span>→</span>
                                </button>
                              </div>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </div>
                )}
              </>
            ) : !loading ? (
              <div className="text-center py-8 text-gray-500">
                {job.status === "completed" 
                  ? (lang === "PL" ? "Brak szczegółowych wyników" : "No detailed results available")
                  : `Job status: ${job.status}.`
                }
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* ======================== QA VERDICT PANEL ======================== */}
      {job.status === "completed" && (
        <QAVerdictPanel 
          jobId={job.id} 
          clientName={(job as any).client_name || ""}
          lang={lang}
          onSaveSuccess={onBackToDashboard}
        />
      )}
    </div>
  );
};

export default VideoComparison;
