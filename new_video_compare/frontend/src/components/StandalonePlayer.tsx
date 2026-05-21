import React, { useState, useEffect, useRef } from "react";
import {
  PlayIcon,
  PauseIcon,
  StopIcon,
  ArrowPathIcon,
  XMarkIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ArrowUpTrayIcon,
} from "@heroicons/react/24/outline";

interface VideoFile {
  url: string;
  name: string;
  size: number;
  isLocal: boolean; // True if using URL.createObjectURL, false if streamed from backend
  fileId?: number;  // Optional, if uploaded to backend
}

export const StandalonePlayer: React.FC = () => {
  const [acceptanceFile, setAcceptanceFile] = useState<VideoFile | null>(null);
  const [emissionFile, setEmissionFile] = useState<VideoFile | null>(null);

  // Loading/Transcoding States for Backend MXF/MOV Path
  const [acceptanceLoading, setAcceptanceLoading] = useState(false);
  const [emissionLoading, setEmissionLoading] = useState(false);
  const [acceptanceLoadingMessage, setAcceptanceLoadingMessage] = useState("");
  const [emissionLoadingMessage, setEmissionLoadingMessage] = useState("");
  const [acceptanceProgress, setAcceptanceProgress] = useState<number | null>(null);
  const [emissionProgress, setEmissionProgress] = useState<number | null>(null);
  const [acceptanceError, setAcceptanceError] = useState<string | null>(null);
  const [emissionError, setEmissionError] = useState<string | null>(null);

  // Active polling refs to manage async timeouts and prevent memory leaks
  const activePollsRef = useRef<{ acceptance?: NodeJS.Timeout; emission?: NodeJS.Timeout }>({});

  // Playback States
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [acceptanceVolume, setAcceptanceVolume] = useState(1);
  const [emissionVolume, setEmissionVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Drag-and-drop highlighting states
  const [isDraggingAcceptance, setIsDraggingAcceptance] = useState(false);
  const [isDraggingEmission, setIsDraggingEmission] = useState(false);

  // Video Refs
  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);

  // Check if a file is standard browser playable (like .mp4)
  const isBrowserPlayable = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    return ext === "mp4" || ext === "webm";
  };

  // Helper to format file size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  // Clean up object URLs to prevent memory leaks
  const cleanUpFile = (file: VideoFile | null) => {
    if (file && file.isLocal && file.url.startsWith("blob:")) {
      URL.revokeObjectURL(file.url);
    }
  };

  // Handle Drag & Drop Events
  const handleDragEnter = (e: React.DragEvent, type: "acceptance" | "emission") => {
    e.preventDefault();
    e.stopPropagation();
    if (type === "acceptance") setIsDraggingAcceptance(true);
    else setIsDraggingEmission(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragLeave = (e: React.DragEvent, type: "acceptance" | "emission") => {
    e.preventDefault();
    e.stopPropagation();
    if (type === "acceptance") setIsDraggingAcceptance(false);
    else setIsDraggingEmission(false);
  };

  // Upload/Process non-native video file (like MXF)
  const uploadAndProcess = async (file: File, type: "acceptance" | "emission") => {
    const isAcc = type === "acceptance";
    let startedPolling = false;

    if (isAcc) {
      // Clear previous poll if any
      if (activePollsRef.current.acceptance) {
        clearTimeout(activePollsRef.current.acceptance);
        activePollsRef.current.acceptance = undefined;
      }
      setAcceptanceLoading(true);
      setAcceptanceError(null);
      setAcceptanceProgress(0);
      setAcceptanceLoadingMessage("Wysyłanie wideo na serwer...");
    } else {
      // Clear previous poll if any
      if (activePollsRef.current.emission) {
        clearTimeout(activePollsRef.current.emission);
        activePollsRef.current.emission = undefined;
      }
      setEmissionLoading(true);
      setEmissionError(null);
      setEmissionProgress(0);
      setEmissionLoadingMessage("Wysyłanie wideo na serwer...");
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", type);

    try {
      const response = await fetch("/api/v1/files/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload nie powiódł się, status: ${response.status}`);
      }

      const data = await response.json();
      const fileId = data.file_id;

      // Start asynchronous background transcode polling
      startedPolling = true;
      const startTime = Date.now();

      const pollStatus = async () => {
        try {
          const statusRes = await fetch(`/api/v1/files/${fileId}`);
          if (!statusRes.ok) {
            throw new Error(`Błąd pobierania statusu: ${statusRes.status}`);
          }
          const fileStatus = await statusRes.json();

          if (fileStatus.is_processed) {
            // Processing success!
            const newFile: VideoFile = {
              url: (() => {
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                  const port = window.location.port;
                  if (port === '3000' || port === '3001') {
                    const backendPort = parseInt(port) + 5001;
                    return `http://localhost:${backendPort}/api/v1/files/stream/${fileId}`;
                  }
                  return `http://localhost:8001/api/v1/files/stream/${fileId}`;
                }
                return `/api/v1/files/stream/${fileId}`;
              })(),
              name: file.name,
              size: file.size,
              isLocal: false,
              fileId: fileId,
            };

            if (isAcc) {
              cleanUpFile(acceptanceFile);
              setAcceptanceFile(newFile);
              setAcceptanceLoading(false);
              setAcceptanceProgress(null);
              setAcceptanceLoadingMessage("");
              if (activePollsRef.current.acceptance) {
                clearTimeout(activePollsRef.current.acceptance);
                activePollsRef.current.acceptance = undefined;
              }
            } else {
              cleanUpFile(emissionFile);
              setEmissionFile(newFile);
              setEmissionLoading(false);
              setEmissionProgress(null);
              setEmissionLoadingMessage("");
              if (activePollsRef.current.emission) {
                clearTimeout(activePollsRef.current.emission);
                activePollsRef.current.emission = undefined;
              }
            }
          } else if (fileStatus.processing_error) {
            // Transcoding failed on FFmpeg side
            throw new Error(fileStatus.processing_error);
          } else {
            // Still processing, update elapsed time and queue next poll
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const progress = fileStatus.file_metadata?.transcode_progress;
            
            if (isAcc) {
              if (typeof progress === "number") {
                setAcceptanceProgress(progress);
                setAcceptanceLoadingMessage(`Transkodowanie wideo... ${progress}% (upłynęło ${elapsed}s)`);
              } else {
                setAcceptanceLoadingMessage(`Transkodowanie wideo... (upłynęło ${elapsed}s)`);
              }
              activePollsRef.current.acceptance = setTimeout(pollStatus, 2000);
            } else {
              if (typeof progress === "number") {
                setEmissionProgress(progress);
                setEmissionLoadingMessage(`Transkodowanie wideo... ${progress}% (upłynęło ${elapsed}s)`);
              } else {
                setEmissionLoadingMessage(`Transkodowanie wideo... (upłynęło ${elapsed}s)`);
              }
              activePollsRef.current.emission = setTimeout(pollStatus, 2000);
            }
          }
        } catch (pollErr: any) {
          console.error(`Błąd w trakcie odpytywania statusu ${type}:`, pollErr);
          const errorMsg = pollErr.message || "Błąd transkodowania pliku wideo.";
          if (isAcc) {
            setAcceptanceError(errorMsg);
            setAcceptanceLoading(false);
            setAcceptanceProgress(null);
            setAcceptanceLoadingMessage("");
            if (activePollsRef.current.acceptance) {
              clearTimeout(activePollsRef.current.acceptance);
              activePollsRef.current.acceptance = undefined;
            }
          } else {
            setEmissionError(errorMsg);
            setEmissionLoading(false);
            setEmissionProgress(null);
            setEmissionLoadingMessage("");
            if (activePollsRef.current.emission) {
              clearTimeout(activePollsRef.current.emission);
              activePollsRef.current.emission = undefined;
            }
          }
        }
      };

      // Trigger initial poll after 1s
      if (isAcc) {
        activePollsRef.current.acceptance = setTimeout(pollStatus, 1000);
      } else {
        activePollsRef.current.emission = setTimeout(pollStatus, 1000);
      }

    } catch (err: any) {
      console.error(`Błąd przesyłania/przetwarzania pliku ${type}:`, err);
      const errorMsg = err.message || "Nie udało się przesłać i przetworzyć wideo.";
      if (isAcc) {
        setAcceptanceError(errorMsg);
      } else {
        setEmissionError(errorMsg);
      }
    } finally {
      // If we failed before polling started, clear loading state immediately
      if (!startedPolling) {
        if (isAcc) {
          setAcceptanceLoading(false);
          setAcceptanceLoadingMessage("");
        } else {
          setEmissionLoading(false);
          setEmissionLoadingMessage("");
        }
      }
    }
  };

  const handleDrop = (e: React.DragEvent, type: "acceptance" | "emission") => {
    e.preventDefault();
    e.stopPropagation();
    
    if (type === "acceptance") setIsDraggingAcceptance(false);
    else setIsDraggingEmission(false);

    const files = e.dataTransfer.files;
    if (files.length === 0) return;

    const file = files[0];
    const isAcc = type === "acceptance";

    // Handle Local vs Transcode path
    if (isBrowserPlayable(file.name)) {
      const localUrl = URL.createObjectURL(file);
      const newFile: VideoFile = {
        url: localUrl,
        name: file.name,
        size: file.size,
        isLocal: true,
      };

      if (isAcc) {
        cleanUpFile(acceptanceFile);
        setAcceptanceFile(newFile);
        setAcceptanceError(null);
      } else {
        cleanUpFile(emissionFile);
        setEmissionFile(newFile);
        setEmissionError(null);
      }
    } else {
      // MXF or ProRes MOV: Needs backend transcoding
      uploadAndProcess(file, type);
    }
  };

  // Synchronized Playback Handlers
  const togglePlayPause = () => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    if (isPlaying) {
      videos.forEach((video) => video?.pause());
    } else {
      // Seek both to current timeline before playing to maintain strict sync
      if (acceptanceVideoRef.current) acceptanceVideoRef.current.currentTime = currentTime;
      if (emissionVideoRef.current) emissionVideoRef.current.currentTime = currentTime;
      videos.forEach((video) => video?.play());
    }
    setIsPlaying(!isPlaying);
  };

  const handleStop = () => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => {
      if (video) {
        video.pause();
        video.currentTime = 0;
      }
    });
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handleRefresh = () => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    videos.forEach((video) => {
      if (video) {
        video.load(); // Force reload the media element to clear buffers
        video.currentTime = 0;
      }
    });
    // If it was playing, resume playback after refresh
    if (isPlaying) {
      setTimeout(() => {
        videos.forEach((video) => video?.play());
      }, 50);
    }
    setCurrentTime(0);
  };

  const handleClear = () => {
    handleStop();
    
    // Clear any active transcode polling timers to prevent leaks
    if (activePollsRef.current.acceptance) {
      clearTimeout(activePollsRef.current.acceptance);
      activePollsRef.current.acceptance = undefined;
    }
    if (activePollsRef.current.emission) {
      clearTimeout(activePollsRef.current.emission);
      activePollsRef.current.emission = undefined;
    }

    cleanUpFile(acceptanceFile);
    cleanUpFile(emissionFile);
    setAcceptanceFile(null);
    setEmissionFile(null);
    setAcceptanceLoading(false);
    setEmissionLoading(false);
    setAcceptanceLoadingMessage("");
    setEmissionLoadingMessage("");
    setAcceptanceProgress(null);
    setEmissionProgress(null);
    setAcceptanceError(null);
    setEmissionError(null);
    setDuration(0);
    setCurrentTime(0);
  };

  const handleSeek = (time: number) => {
    if (acceptanceVideoRef.current) {
      acceptanceVideoRef.current.currentTime = time;
    }
    if (emissionVideoRef.current) {
      emissionVideoRef.current.currentTime = time;
    }
    setCurrentTime(time);
  };

  // Sync individual volumes & master mute state
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

  // Sync playhead, duration, and track status
  useEffect(() => {
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];

    const handleLoadedMetadata = () => {
      // Set duration based on the longest loaded video
      const accDur = acceptanceVideoRef.current?.duration || 0;
      const emiDur = emissionVideoRef.current?.duration || 0;
      setDuration(Math.max(accDur, emiDur));
    };

    const handleTimeUpdate = () => {
      // Use acceptance video as the sync master by default
      if (acceptanceVideoRef.current) {
        const accTime = acceptanceVideoRef.current.currentTime;
        setCurrentTime(accTime);

        // Keep the second video in lock-step (threshold of 0.15 seconds)
        if (emissionVideoRef.current && isPlaying) {
          if (Math.abs(emissionVideoRef.current.currentTime - accTime) > 0.15) {
            emissionVideoRef.current.currentTime = accTime;
          }
        }
      } else if (emissionVideoRef.current) {
        // Fallback to emission video if acceptance is not loaded
        setCurrentTime(emissionVideoRef.current.currentTime);
      }
    };

    const handleEnded = () => {
      // Check if both loaded videos are completed
      const accEnded = acceptanceVideoRef.current ? acceptanceVideoRef.current.ended : true;
      const emiEnded = emissionVideoRef.current ? emissionVideoRef.current.ended : true;
      if (accEnded && emiEnded) {
        setIsPlaying(false);
      }
    };

    videos.forEach((video) => {
      if (video) {
        video.addEventListener("loadedmetadata", handleLoadedMetadata);
        video.addEventListener("timeupdate", handleTimeUpdate);
        video.addEventListener("ended", handleEnded);
      }
    });

    return () => {
      videos.forEach((video) => {
        if (video) {
          video.removeEventListener("loadedmetadata", handleLoadedMetadata);
          video.removeEventListener("timeupdate", handleTimeUpdate);
          video.removeEventListener("ended", handleEnded);
        }
      });
    };
  }, [acceptanceFile, emissionFile, isPlaying]);

  // Clean up Object URLs and active polling timeouts when component unmounts
  useEffect(() => {
    const currentPolls = activePollsRef.current;
    return () => {
      cleanUpFile(acceptanceFile);
      cleanUpFile(emissionFile);
      
      // Clear all active background timeouts
      if (currentPolls.acceptance) {
        clearTimeout(currentPolls.acceptance);
      }
      if (currentPolls.emission) {
        clearTimeout(currentPolls.emission);
      }
      setAcceptanceProgress(null);
      setEmissionProgress(null);
    };
  }, [acceptanceFile, emissionFile]);

  // Format MM:SS for timeline
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 pb-20">
      {/* Title Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-1">Niezależny Odtwarzacz Synchroniczny</h2>
        <p className="text-gray-500 text-sm">
          Przeciągnij i upuść pliki wideo, aby odtworzyć je obok siebie w pełnej synchronizacji. Obsługuje formaty MP4, MOV oraz MXF.
        </p>
      </div>

      {/* Video Panels Area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        
        {/* Acceptance Video Panel */}
        <div
          onDragEnter={(e) => handleDragEnter(e, "acceptance")}
          onDragOver={handleDragOver}
          onDragLeave={(e) => handleDragLeave(e, "acceptance")}
          onDrop={(e) => handleDrop(e, "acceptance")}
          className={`bg-white rounded-2xl shadow-sm border overflow-hidden transition-all duration-200 ${
            isDraggingAcceptance ? "border-green-500 ring-4 ring-green-100 scale-[1.01]" : "border-gray-200"
          }`}
        >
          {/* Header Panel */}
          <div className="px-6 py-4 border-b border-gray-100 bg-green-50/50 flex justify-between items-center">
            <div>
              <h3 className="font-semibold text-green-800">Wideo Akceptacyjne (Acceptance)</h3>
              {acceptanceFile && (
                <p className="text-xs text-gray-500 truncate max-w-[300px] mt-0.5" title={acceptanceFile.name}>
                  {acceptanceFile.name} • {formatFileSize(acceptanceFile.size)}
                </p>
              )}
            </div>
            {acceptanceFile && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-800 uppercase">
                {acceptanceFile.isLocal ? "Lokalny" : "Serwer"}
              </span>
            )}
          </div>

          {/* Player Container */}
          <div className="p-4 bg-gray-50/40 relative aspect-video flex items-center justify-center">
            {acceptanceLoading && (
              <div className="absolute inset-0 z-30 bg-gray-950/85 backdrop-blur-sm flex flex-col items-center justify-center text-white p-6 text-center transition-all duration-200">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-green-500 border-t-transparent mb-4 shadow-lg shadow-green-500/20"></div>
                <p className="font-semibold text-base text-gray-100 tracking-wide mb-3">{acceptanceLoadingMessage || "Przetwarzanie wideo..."}</p>
                {acceptanceProgress !== null && acceptanceProgress > 0 && (
                  <div className="w-full max-w-xs bg-gray-800 rounded-full h-2.5 mb-3 overflow-hidden border border-gray-700 shadow-inner">
                    <div 
                      className="bg-green-500 h-full rounded-full transition-all duration-300 ease-out shadow-[0_0_8px_rgba(34,197,94,0.6)]" 
                      style={{ width: `${acceptanceProgress}%` }}
                    ></div>
                  </div>
                )}
                <p className="text-xs text-gray-400 font-mono bg-gray-900/60 px-3 py-1 rounded-full border border-gray-800/40">
                  Optymalne transkodowanie w tle (CPU z limitem wątków)
                </p>
              </div>
            )}

            {acceptanceError && (
              <div className="absolute inset-0 z-30 bg-red-50 p-6 flex flex-col items-center justify-center text-center">
                <p className="text-red-600 font-semibold mb-2">Błąd Ładowania Wideo</p>
                <p className="text-xs text-red-500 max-w-sm mb-4">{acceptanceError}</p>
                <button
                  onClick={() => setAcceptanceError(null)}
                  className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                >
                  Zamknij
                </button>
              </div>
            )}

            {acceptanceFile ? (
              <video
                ref={acceptanceVideoRef}
                className="w-full h-full object-contain bg-black rounded-lg"
                src={acceptanceFile.url}
                crossOrigin="anonymous"
                preload="auto"
                onError={() => {
                  setAcceptanceError("Nie udało się załadować strumienia wideo z serwera (np. plik wygasł w trybie DEV lub brak połączenia).");
                }}
              />
            ) : (
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center p-6 text-center text-gray-400 bg-white">
                <ArrowUpTrayIcon className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-semibold text-gray-700">Przeciągnij i upuść Wideo Akceptacyjne</p>
                <p className="text-xs text-gray-400 mt-1">Obsługuje MP4, MOV, MXF</p>
              </div>
            )}
          </div>

          {/* Volume control */}
          <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center space-x-3">
            <button
              disabled={!acceptanceFile}
              onClick={() => {
                if (acceptanceVolume > 0) setAcceptanceVolume(0);
                else setAcceptanceVolume(1);
              }}
              className="p-1 text-gray-500 hover:text-gray-700 disabled:opacity-40"
            >
              {acceptanceVolume === 0 || isMuted ? (
                <SpeakerXMarkIcon className="w-4 h-4 text-gray-400" />
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
              onChange={(e) => setAcceptanceVolume(parseFloat(e.target.value))}
              disabled={!acceptanceFile}
              className="w-28 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-600 disabled:opacity-40"
            />
            <span className="text-[10px] text-gray-400 w-8 tabular-nums font-semibold">
              {Math.round((isMuted ? 0 : acceptanceVolume) * 100)}%
            </span>
          </div>
        </div>

        {/* Emission Video Panel */}
        <div
          onDragEnter={(e) => handleDragEnter(e, "emission")}
          onDragOver={handleDragOver}
          onDragLeave={(e) => handleDragLeave(e, "emission")}
          onDrop={(e) => handleDrop(e, "emission")}
          className={`bg-white rounded-2xl shadow-sm border overflow-hidden transition-all duration-200 ${
            isDraggingEmission ? "border-red-500 ring-4 ring-red-100 scale-[1.01]" : "border-gray-200"
          }`}
        >
          {/* Header Panel */}
          <div className="px-6 py-4 border-b border-gray-100 bg-red-50/50 flex justify-between items-center">
            <div>
              <h3 className="font-semibold text-red-800">Wideo Emisyjne (Emission)</h3>
              {emissionFile && (
                <p className="text-xs text-gray-500 truncate max-w-[300px] mt-0.5" title={emissionFile.name}>
                  {emissionFile.name} • {formatFileSize(emissionFile.size)}
                </p>
              )}
            </div>
            {emissionFile && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 uppercase">
                {emissionFile.isLocal ? "Lokalny" : "Serwer"}
              </span>
            )}
          </div>

          {/* Player Container */}
          <div className="p-4 bg-gray-50/40 relative aspect-video flex items-center justify-center">
            {emissionLoading && (
              <div className="absolute inset-0 z-30 bg-gray-950/85 backdrop-blur-sm flex flex-col items-center justify-center text-white p-6 text-center transition-all duration-200">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-red-500 border-t-transparent mb-4 shadow-lg shadow-red-500/20"></div>
                <p className="font-semibold text-base text-gray-100 tracking-wide mb-3">{emissionLoadingMessage || "Przetwarzanie wideo..."}</p>
                {emissionProgress !== null && emissionProgress > 0 && (
                  <div className="w-full max-w-xs bg-gray-800 rounded-full h-2.5 mb-3 overflow-hidden border border-gray-700 shadow-inner">
                    <div 
                      className="bg-red-500 h-full rounded-full transition-all duration-300 ease-out shadow-[0_0_8px_rgba(239,68,68,0.6)]" 
                      style={{ width: `${emissionProgress}%` }}
                    ></div>
                  </div>
                )}
                <p className="text-xs text-gray-400 font-mono bg-gray-900/60 px-3 py-1 rounded-full border border-gray-800/40">
                  Optymalne transkodowanie w tle (CPU z limitem wątków)
                </p>
              </div>
            )}

            {emissionError && (
              <div className="absolute inset-0 z-30 bg-red-50 p-6 flex flex-col items-center justify-center text-center">
                <p className="text-red-600 font-semibold mb-2">Błąd Ładowania Wideo</p>
                <p className="text-xs text-red-500 max-w-sm mb-4">{emissionError}</p>
                <button
                  onClick={() => setEmissionError(null)}
                  className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                >
                  Zamknij
                </button>
              </div>
            )}

            {emissionFile ? (
              <video
                ref={emissionVideoRef}
                className="w-full h-full object-contain bg-black rounded-lg"
                src={emissionFile.url}
                crossOrigin="anonymous"
                preload="auto"
                onError={() => {
                  setEmissionError("Nie udało się załadować strumienia wideo z serwera (np. plik wygasł w trybie DEV lub brak połączenia).");
                }}
              />
            ) : (
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center p-6 text-center text-gray-400 bg-white">
                <ArrowUpTrayIcon className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-semibold text-gray-700">Przeciągnij i upuść Wideo Emisyjne</p>
                <p className="text-xs text-gray-400 mt-1">Obsługuje MP4, MOV, MXF</p>
              </div>
            )}
          </div>

          {/* Volume control */}
          <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center space-x-3">
            <button
              disabled={!emissionFile}
              onClick={() => {
                if (emissionVolume > 0) setEmissionVolume(0);
                else setEmissionVolume(1);
              }}
              className="p-1 text-gray-500 hover:text-gray-700 disabled:opacity-40"
            >
              {emissionVolume === 0 || isMuted ? (
                <SpeakerXMarkIcon className="w-4 h-4 text-gray-400" />
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
              onChange={(e) => setEmissionVolume(parseFloat(e.target.value))}
              disabled={!emissionFile}
              className="w-28 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-600 disabled:opacity-40"
            />
            <span className="text-[10px] text-gray-400 w-8 tabular-nums font-semibold">
              {Math.round((isMuted ? 0 : emissionVolume) * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* Synchronized Playback Control Dashboard */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          
          {/* Timeline and Seek Bar */}
          <div className="flex-grow flex items-center space-x-4">
            <span className="text-sm text-gray-500 font-mono w-12 text-right">
              {formatTime(currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={duration || 100}
              step="0.01"
              value={currentTime}
              onChange={(e) => handleSeek(parseFloat(e.target.value))}
              disabled={!acceptanceFile && !emissionFile}
              className="flex-grow h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 disabled:opacity-40"
            />
            <span className="text-sm text-gray-500 font-mono w-12">
              {formatTime(duration)}
            </span>
          </div>

          {/* Navigation Control Buttons */}
          <div className="flex items-center justify-center space-x-3 flex-shrink-0">
            {/* Play/Pause Button */}
            <button
              onClick={togglePlayPause}
              disabled={!acceptanceFile && !emissionFile}
              className={`w-12 h-12 flex items-center justify-center text-white rounded-full transition-all shadow-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${
                !acceptanceFile && !emissionFile
                  ? "bg-gray-300 shadow-none cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700 shadow-blue-600/10"
              }`}
              title="Odtwarzaj / Pauza"
            >
              {isPlaying ? <PauseIcon className="w-5 h-5" /> : <PlayIcon className="w-5 h-5 ml-0.5" />}
            </button>

            {/* Stop Button */}
            <button
              onClick={handleStop}
              disabled={!acceptanceFile && !emissionFile}
              className="w-10 h-10 flex items-center justify-center bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-gray-100"
              title="Zatrzymaj"
            >
              <StopIcon className="w-5 h-5" />
            </button>

            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={!acceptanceFile && !emissionFile}
              className="w-10 h-10 flex items-center justify-center bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-gray-100"
              title="Odśwież / Przeładuj"
            >
              <ArrowPathIcon className="w-5 h-5" />
            </button>

            <div className="h-6 w-px bg-gray-200 mx-1"></div>

            {/* Clear Button */}
            <button
              onClick={handleClear}
              disabled={!acceptanceFile && !emissionFile}
              className="w-10 h-10 flex items-center justify-center bg-gray-100 hover:bg-red-50 hover:text-red-600 text-gray-600 rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-gray-100"
              title="Wyczyść odtwarzacze"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>

            <div className="h-6 w-px bg-gray-200 mx-1"></div>

            {/* Global Mute Button */}
            <button
              onClick={() => setIsMuted(!isMuted)}
              disabled={!acceptanceFile && !emissionFile}
              className={`w-10 h-10 flex items-center justify-center rounded-xl transition-colors disabled:opacity-40 ${
                isMuted ? "bg-red-50 text-red-600" : "bg-gray-100 hover:bg-gray-200 text-gray-600"
              }`}
              title="Wycisz wszystko"
            >
              {isMuted ? <SpeakerXMarkIcon className="w-5 h-5" /> : <SpeakerWaveIcon className="w-5 h-5" />}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
