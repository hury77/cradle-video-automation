import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  PlayIcon,
  PauseIcon,
  StopIcon,
  ArrowPathIcon,
  XMarkIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  ArrowUpTrayIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  EyeIcon,
  EyeSlashIcon,
  CameraIcon,
  EyeDropperIcon,
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

  // Resolution States
  const [accDimensions, setAccDimensions] = useState<{width: number, height: number} | null>(null);
  const [emDimensions, setEmDimensions] = useState<{width: number, height: number} | null>(null);

  // Eyedropper States
  const [isEyedropperActive, setIsEyedropperActive] = useState(false);
  const [hoverColor, setHoverColor] = useState<{ r: number, g: number, b: number, hex: string, x: number, y: number, sourceX: number, sourceY: number, sourceVideo: "acceptance" | "emission" } | null>(null);

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

  // ── Diff Overlay State ────────────────────────────────────────────────────
  const [diffMode, setDiffMode] = useState(false);
  const [wipePosition, setWipePosition] = useState(50); // 0-100%
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [diffTimestamps, setDiffTimestamps] = useState<
    { time: number; severity: "certain" | "review" }[]
  >([]);
  const [screenshotSaving, setScreenshotSaving] = useState(false);

  // Video Refs
  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);

  // Diff overlay refs
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const diffWorkerRef = useRef<Worker | null>(null);
  const analysisIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const wipeContainerRef = useRef<HTMLDivElement>(null);
  const isDraggingWipeRef = useRef(false);
  // Track already-logged timestamps (keyed by rounded second)
  const loggedTimesRef = useRef<Set<number>>(new Set());
  // Canvas-based wipe display (draws directly from main video refs - no extra <video> elements)
  const wipeCanvasRef = useRef<HTMLCanvasElement>(null);
  // Mirror of wipePosition for use inside RAF closure (avoids stale state)
  const wipePositionRef = useRef(50);
  // requestAnimationFrame handle
  const rafIdRef = useRef<number | null>(null);

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
                // Use REACT_APP_API_URL env var (set at startup per environment)
                // LIVE: http://localhost:8001, DEV: http://localhost:8002
                const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8001';
                return `${apiBase}/api/v1/files/stream/${fileId}`;
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
      // Attach .catch() DIRECTLY to the play promise to prevent React Error Overlay from intercepting it
      videos.forEach((video) => {
        if (video) {
          const playPromise = video.play();
          if (playPromise !== undefined) {
            playPromise.catch((err: any) => {
              if (err?.name !== 'AbortError') {
                console.error('[Player] play() error:', err);
              }
            });
          }
        }
      });
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
    // IMPORTANT: Do NOT call video.load() here — it resets the element to HAVE_NOTHING
    // state and causes onError to fire before the video can rebuffer, crashing both players.
    // Simply seeking to 0 is safe for both blob URLs and server streams.
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    const wasPlaying = isPlaying;

    // Pause both videos first
    videos.forEach((video) => video?.pause());
    setIsPlaying(false);

    // Seek both to start — use canplay event to ensure video is ready before playing
    let readyCount = 0;
    const totalActive = videos.filter(Boolean).length;

    videos.forEach((video) => {
      if (!video) return;

      const onSeeked = () => {
        video.removeEventListener('seeked', onSeeked);
        readyCount++;
        if (wasPlaying && readyCount >= totalActive) {
          // Both seeked — resume playback
          videos.forEach((v) => {
            if (v) {
              const playPromise = v.play();
              if (playPromise !== undefined) {
                playPromise.catch((err: any) => {
                  if (err?.name !== 'AbortError') {
                    console.error('[Player] refresh play() error:', err);
                  }
                });
              }
            }
          });
          setIsPlaying(true);
        }
      };

      video.addEventListener('seeked', onSeeked);
      video.currentTime = 0;
    });

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

  const handleMouseMove = (e: React.MouseEvent<HTMLVideoElement>, videoRef: React.RefObject<HTMLVideoElement | null>) => {
    if (!isEyedropperActive || isPlaying || !videoRef.current) {
      if (hoverColor) setHoverColor(null);
      return;
    }
    
    const video = videoRef.current;
    if (video.readyState < 2) return;

    const rect = video.getBoundingClientRect();
    const videoRatio = video.videoWidth / video.videoHeight;
    const containerRatio = rect.width / rect.height;

    let renderedWidth, renderedHeight, offsetX = 0, offsetY = 0;
    if (containerRatio > videoRatio) {
      renderedHeight = rect.height;
      renderedWidth = rect.height * videoRatio;
      offsetX = (rect.width - renderedWidth) / 2;
    } else {
      renderedWidth = rect.width;
      renderedHeight = rect.width / videoRatio;
      offsetY = (rect.height - renderedHeight) / 2;
    }

    const mouseX = e.clientX - rect.left - offsetX;
    const mouseY = e.clientY - rect.top - offsetY;

    if (mouseX < 0 || mouseX > renderedWidth || mouseY < 0 || mouseY > renderedHeight) {
      // Usunięto czyszczenie, by kolor nie znikał przy krawędziach / robieniu screena
      return;
    }

    const sourceX = (mouseX / renderedWidth) * video.videoWidth;
    const sourceY = (mouseY / renderedHeight) * video.videoHeight;

    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;

    try {
      ctx.drawImage(video, sourceX, sourceY, 1, 1, 0, 0, 1, 1);
      const pixel = ctx.getImageData(0, 0, 1, 1).data;
      
      const r = pixel[0], g = pixel[1], b = pixel[2];
      const hex = "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();

      const sourceVideo = videoRef === acceptanceVideoRef ? "acceptance" : "emission";
      setHoverColor({ r, g, b, hex, x: e.clientX, y: e.clientY, sourceX, sourceY, sourceVideo });
    } catch (err) {
      setHoverColor(null);
    }
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

  const handleStep = (frames: number) => {
    // Zakładamy 25 fps jako standard dla broadcast
    const fps = 25;
    const stepTime = frames / fps; 
    const newTime = Math.max(0, Math.min(currentTime + stepTime, duration));
    
    const videos = [acceptanceVideoRef.current, emissionVideoRef.current];
    if (isPlaying) {
      videos.forEach((video) => video?.pause());
      setIsPlaying(false);
    }
    
    handleSeek(newTime);
  };

  // ── Diff Overlay Logic ───────────────────────────────────────────────────

  /** Teleport both players to a specific timestamp and pause */
  const teleportToTimestamp = useCallback((time: number) => {
    if (acceptanceVideoRef.current) {
      acceptanceVideoRef.current.pause();
      acceptanceVideoRef.current.currentTime = time;
    }
    if (emissionVideoRef.current) {
      emissionVideoRef.current.pause();
      emissionVideoRef.current.currentTime = time;
    }
    setIsPlaying(false);
    setCurrentTime(time);
  }, []);

  /** Capture one frame from each video, diff them in the Worker, paint overlay */
  const analyzeCurrentFrame = useCallback(() => {
    const accVideo = acceptanceVideoRef.current;
    const emiVideo = emissionVideoRef.current;
    const canvas = overlayCanvasRef.current;
    if (!accVideo || !emiVideo || !canvas || !diffWorkerRef.current) return;
    if (accVideo.readyState < 2 || emiVideo.readyState < 2) return;

    // Use the smaller of the two resolutions to avoid stretching
    const W = Math.min(accVideo.videoWidth  || 1280, 1280);
    const H = Math.min(accVideo.videoHeight || 720,  720);
    if (W === 0 || H === 0) return;

    canvas.width  = W;
    canvas.height = H;

    // Temporary canvas to extract pixel data
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width = W;
    tmpCanvas.height = H;
    const tmpCtx = tmpCanvas.getContext("2d", { willReadFrequently: true })!;

    tmpCtx.drawImage(accVideo, 0, 0, W, H);
    const accData = tmpCtx.getImageData(0, 0, W, H);

    tmpCtx.clearRect(0, 0, W, H);
    tmpCtx.drawImage(emiVideo, 0, 0, W, H);
    const emiData = tmpCtx.getImageData(0, 0, W, H);

    diffWorkerRef.current.postMessage(
      { acceptanceData: accData, emissionData: emiData, width: W, height: H },
      [accData.data.buffer, emiData.data.buffer]
    );
  }, []);

  /** Start diff mode: create Worker, begin periodic analysis */
  const activateDiffMode = useCallback(() => {
    if (!acceptanceVideoRef.current || !emissionVideoRef.current) return;

    // Create off-screen canvas for the diff overlay output.
    // After the wipe-panel refactor the <canvas ref={overlayCanvasRef}> is no longer
    // in the DOM, so we must create it programmatically — otherwise the worker
    // result is discarded and no highlights are shown.
    const offscreen = document.createElement("canvas");
    offscreen.width  = Math.min(acceptanceVideoRef.current.videoWidth  || 1280, 1280);
    offscreen.height = Math.min(acceptanceVideoRef.current.videoHeight || 720,  720);
    overlayCanvasRef.current = offscreen;

    // Create Web Worker inline via Blob to avoid CRA webpack Worker loader issues
    const workerCode = `
      const THRESHOLD_AUTOMATION = 30;
      const THRESHOLD_REVIEW = 15;
      self.onmessage = function(e) {
        var acceptanceData = e.data.acceptanceData;
        var emissionData   = e.data.emissionData;
        var width  = e.data.width;
        var height = e.data.height;
        var total  = width * height;
        var overlay = new Uint8ClampedArray(total * 4);
        var certain = 0, review = 0;
        for (var i = 0; i < total; i++) {
          var idx = i * 4;
          var dr = Math.abs(acceptanceData.data[idx]   - emissionData.data[idx]);
          var dg = Math.abs(acceptanceData.data[idx+1] - emissionData.data[idx+1]);
          var db = Math.abs(acceptanceData.data[idx+2] - emissionData.data[idx+2]);
          var m  = Math.max(dr, dg, db);
          if (m > THRESHOLD_AUTOMATION) {
            overlay[idx]=255; overlay[idx+1]=0;   overlay[idx+2]=0;   overlay[idx+3]=230;
            certain++;
          } else if (m > THRESHOLD_REVIEW) {
            overlay[idx]=255; overlay[idx+1]=200; overlay[idx+2]=0;   overlay[idx+3]=200;
            review++;
          } else {
            overlay[idx+3]=0;
          }
        }
        var img = new ImageData(overlay, width, height);
        self.postMessage(
          { overlayData: img, certaintDiffRatio: certain/total, reviewDiffRatio: review/total, hasDifferences: certain>0||review>0 },
          [img.data.buffer]
        );
      };
    `;
    const blob = new Blob([workerCode], { type: "application/javascript" });
    const worker = new Worker(URL.createObjectURL(blob));
    diffWorkerRef.current = worker;

    worker.onmessage = (e: MessageEvent) => {
      const { overlayData, certaintDiffRatio, reviewDiffRatio } = e.data;
      const canvas = overlayCanvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d")!;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (overlayData) ctx.putImageData(overlayData, 0, 0);

      // Log timestamps
      const time = acceptanceVideoRef.current?.currentTime ?? 0;
      const roundedTime = Math.floor(time);
      if (!loggedTimesRef.current.has(roundedTime)) {
        const isCertain = certaintDiffRatio > 0.005;  // >0.5% pixels certain
        const isReview  = reviewDiffRatio   > 0.02;   // >2% pixels review
        if (isCertain || isReview) {
          loggedTimesRef.current.add(roundedTime);
          setDiffTimestamps(prev => [
            ...prev,
            { time, severity: isCertain ? "certain" : "review" }
          ]);
        }
      }
    };

    setDiffMode(true);
    setIsAnalyzing(true);
    loggedTimesRef.current.clear();
    setDiffTimestamps([]);

    // Analyze once immediately, then every 500ms during playback
    analyzeCurrentFrame();
    analysisIntervalRef.current = setInterval(() => {
      if (!acceptanceVideoRef.current?.paused) {
        analyzeCurrentFrame();
      }
    }, 500);
  }, [analyzeCurrentFrame]);

  /** Stop diff mode: terminate Worker, clear overlay */
  const deactivateDiffMode = useCallback(() => {
    if (analysisIntervalRef.current) {
      clearInterval(analysisIntervalRef.current);
      analysisIntervalRef.current = null;
    }
    if (diffWorkerRef.current) {
      diffWorkerRef.current.terminate();
      diffWorkerRef.current = null;
    }
    const canvas = overlayCanvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }
    setDiffMode(false);
    setIsAnalyzing(false);
  }, []);

  /** Clean up worker on unmount */
  useEffect(() => {
    return () => { deactivateDiffMode(); };
  }, [deactivateDiffMode]);

  /** Also run analysis on seek/step when diff mode is active */
  useEffect(() => {
    if (diffMode) {
      analyzeCurrentFrame();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTime, diffMode]);

  // ── Wipe slider mouse handlers ───────────────────────────────────────────
  const handleWipeMouseDown = (e: React.MouseEvent) => {
    isDraggingWipeRef.current = true;
    e.preventDefault();
  };

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isDraggingWipeRef.current || !wipeContainerRef.current) return;
      const rect = wipeContainerRef.current.getBoundingClientRect();
      const pos = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
      setWipePosition(pos);
    };
    const onMouseUp = () => { isDraggingWipeRef.current = false; };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  // Keep wipePositionRef in sync so RAF closure sees the latest value
  useEffect(() => {
    wipePositionRef.current = wipePosition;
  }, [wipePosition]);

  // ── Canvas-based Wipe RAF loop ────────────────────────────────────────────
  // Draws acceptance (clipped) + emission + diff overlay directly from the main
  // video refs. Zero extra <video> elements → no ref hijacking → no freeze.
  useEffect(() => {
    if (!diffMode) {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      return;
    }

    const drawFrame = () => {
      const accVideo = acceptanceVideoRef.current;
      const emiVideo = emissionVideoRef.current;
      const wipeCanvas = wipeCanvasRef.current;
      const overlayCanvas = overlayCanvasRef.current;

      if (!accVideo || !emiVideo || !wipeCanvas) {
        rafIdRef.current = requestAnimationFrame(drawFrame);
        return;
      }

      // Match canvas resolution to its CSS display size
      const W = wipeCanvas.clientWidth  || 1280;
      const H = wipeCanvas.clientHeight || 720;
      if (wipeCanvas.width !== W)  wipeCanvas.width  = W;
      if (wipeCanvas.height !== H) wipeCanvas.height = H;

      const ctx = wipeCanvas.getContext("2d")!;
      ctx.clearRect(0, 0, W, H);

      const wp = wipePositionRef.current;

      // 1. Draw emission full-width (right side / background)
      if (emiVideo.readyState >= 2) {
        ctx.drawImage(emiVideo, 0, 0, W, H);
      }

      // 2. Draw acceptance, clipped to the left portion (wipe position)
      if (accVideo.readyState >= 2 && wp > 0) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, Math.round(W * wp / 100), H);
        ctx.clip();
        ctx.drawImage(accVideo, 0, 0, W, H);
        ctx.restore();
      }

      // 3. Diff overlay (source-over — renders at full color, not washed out by screen blend)
      if (overlayCanvas && overlayCanvas.width > 0) {
        ctx.globalAlpha = 0.72;
        ctx.globalCompositeOperation = "source-over";
        ctx.drawImage(overlayCanvas, 0, 0, W, H);
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "source-over";
      }

      // 4. Wipe divider line + handle
      const lineX = Math.round(W * wp / 100);
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.lineWidth = 2;
      ctx.shadowColor = "rgba(255,255,255,0.6)";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(lineX, 0);
      ctx.lineTo(lineX, H);
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Handle circle
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(lineX, H / 2, 16, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.2)";
      ctx.lineWidth = 1;
      ctx.stroke();
      // Arrows inside circle
      ctx.fillStyle = "#374151";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("❮❯", lineX, H / 2);
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";

      // 5. Corner labels
      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "rgba(34,197,94,0.9)";
      ctx.fillRect(10, 10, 90, 22);
      ctx.fillStyle = "#fff";
      ctx.fillText("ACCEPTANCE", 14, 26);

      ctx.fillStyle = "rgba(239,68,68,0.9)";
      ctx.fillRect(W - 84, 10, 74, 22);
      ctx.fillStyle = "#fff";
      ctx.fillText("EMISSION", W - 80, 26);

      rafIdRef.current = requestAnimationFrame(drawFrame);
    };

    rafIdRef.current = requestAnimationFrame(drawFrame);

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [diffMode]);

  // ── Screenshot ───────────────────────────────────────────────────────────
  const captureScreenshot = useCallback(async () => {
    const accVideo = acceptanceVideoRef.current;
    const emiVideo = emissionVideoRef.current;
    if (!accVideo || !emiVideo) return;

    // Pause first so both frames are stable
    const wasPlaying = !accVideo.paused;
    if (wasPlaying) {
      accVideo.pause();
      emiVideo.pause();
    }

    // Wait one animation frame so the browser has rendered the paused frame
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));

    setScreenshotSaving(true);
    try {
      // Each side: max 960px (total 1920px)
      const SIDE_W = 960;
      const aspectRatio = (accVideo.videoHeight || 720) / (accVideo.videoWidth || 1280);
      const SIDE_H = Math.round(SIDE_W * aspectRatio);
      const LABEL_H = 60;

      const canvas = document.createElement("canvas");
      canvas.width  = SIDE_W * 2;          // 1920px total
      canvas.height = SIDE_H + LABEL_H;
      const ctx = canvas.getContext("2d")!;

      // Dark background
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw frames
      if (accVideo.readyState >= 2) ctx.drawImage(accVideo, 0, LABEL_H, SIDE_W, SIDE_H);
      if (emiVideo.readyState >= 2) ctx.drawImage(emiVideo, SIDE_W, LABEL_H, SIDE_W, SIDE_H);

      // Diff overlay on both sides
      const overlayCanvas = overlayCanvasRef.current;
      if (overlayCanvas && overlayCanvas.width > 0 && diffMode) {
        ctx.globalAlpha = 0.85;
        ctx.globalCompositeOperation = "screen";
        ctx.drawImage(overlayCanvas, 0, LABEL_H, SIDE_W, SIDE_H);
        ctx.drawImage(overlayCanvas, SIDE_W, LABEL_H, SIDE_W, SIDE_H);
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "source-over";
      }

      // Center divider
      ctx.strokeStyle = "rgba(255,255,255,0.5)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(SIDE_W, LABEL_H);
      ctx.lineTo(SIDE_W, canvas.height);
      ctx.stroke();

      // Label bar
      const tc = formatTimecode(accVideo.currentTime);
      // Green strip (acceptance)
      ctx.fillStyle = "#14532d";
      ctx.fillRect(0, 0, SIDE_W, LABEL_H);
      ctx.fillStyle = "#22c55e";
      ctx.font = "bold 18px 'Courier New', monospace";
      ctx.textBaseline = "middle";
      ctx.fillText("ACCEPTANCE", 20, 22);
      ctx.fillStyle = "#86efac";
      ctx.font = "13px 'Courier New', monospace";
      ctx.fillText(acceptanceFile?.name?.slice(0, 40) ?? "", 20, 46);

      // Red strip (emission)
      ctx.fillStyle = "#450a0a";
      ctx.fillRect(SIDE_W, 0, SIDE_W, LABEL_H);
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 18px 'Courier New', monospace";
      ctx.fillText("EMISSION", SIDE_W + 20, 22);
      ctx.fillStyle = "#fca5a5";
      ctx.font = "13px 'Courier New', monospace";
      ctx.fillText(emissionFile?.name?.slice(0, 40) ?? "", SIDE_W + 20, 46);

      // Timecode centered at top
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(SIDE_W - 90, 0, 180, LABEL_H);
      ctx.fillStyle = "#f8fafc";
      ctx.font = "bold 16px 'Courier New', monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(tc, SIDE_W, LABEL_H / 2);
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";

      // Diff legend (bottom-right corner)
      if (diffMode) {
        ctx.fillStyle = "rgba(15,23,42,0.85)";
        ctx.fillRect(canvas.width - 210, canvas.height - 56, 200, 50);
        ctx.fillStyle = "#dc2626";
        ctx.fillRect(canvas.width - 198, canvas.height - 44, 14, 14);
        ctx.fillStyle = "#e2e8f0";
        ctx.font = "12px sans-serif";
        ctx.fillText("Pewna różnica", canvas.width - 178, canvas.height - 33);
        ctx.fillStyle = "#eab308";
        ctx.fillRect(canvas.width - 198, canvas.height - 24, 14, 10);
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText("Do sprawdzenia", canvas.width - 178, canvas.height - 14);
      }

      // Eyedropper dynamic overlay matching cursor position
      if (isEyedropperActive && hoverColor) {
        const isAcc = hoverColor.sourceVideo === "acceptance";
        const scaleX = SIDE_W / (isAcc ? accVideo.videoWidth : emiVideo.videoWidth);
        const scaleY = SIDE_H / (isAcc ? accVideo.videoHeight : emiVideo.videoHeight);
        
        let drawX = hoverColor.sourceX * scaleX;
        let drawY = hoverColor.sourceY * scaleY + LABEL_H;
        if (!isAcc) drawX += SIDE_W;

        // Offset the box slightly from the exact pixel
        drawX += 20;
        drawY += 20;

        // Keep it inside the canvas
        if (drawX + 160 > canvas.width) drawX -= 180;
        if (drawY + 60 > canvas.height) drawY -= 80;

        // Tooltip Background
        ctx.fillStyle = "rgba(15,23,42,0.95)";
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(drawX, drawY, 150, 44, 8);
        } else {
          ctx.fillRect(drawX, drawY, 150, 44);
        }
        ctx.fill();
        ctx.strokeStyle = "rgba(71,85,105,0.5)";
        ctx.stroke();

        // Color Swatch
        ctx.fillStyle = hoverColor.hex;
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(drawX + 8, drawY + 8, 28, 28, 4);
        } else {
          ctx.fillRect(drawX + 8, drawY + 8, 28, 28);
        }
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.2)";
        ctx.stroke();
        
        // Text
        ctx.fillStyle = "#f8fafc";
        ctx.font = "bold 13px 'Courier New', monospace";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(hoverColor.hex, drawX + 44, drawY + 16);
        ctx.fillStyle = "#94a3b8";
        ctx.font = "10px 'Courier New', monospace";
        ctx.fillText(`RGB: ${hoverColor.r}, ${hoverColor.g}, ${hoverColor.b}`, drawX + 44, drawY + 32);
      }

      canvas.toBlob((blob) => {
        if (!blob) return;
        const prefix = (acceptanceFile?.name ?? "screenshot")
          .replace(/\.[^.]+$/, "")
          .slice(0, 15)
          .replace(/[^a-zA-Z0-9_-]/g, "_");
        const tcSafe = tc.replace(/:/g, "-");
        const filename = `${prefix}_${tcSafe}.png`;
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        setScreenshotSaving(false);
        // Resume playback if it was playing before
        if (wasPlaying) {
          accVideo.play().catch(() => {});
          emiVideo.play().catch(() => {});
          setIsPlaying(true);
        }
      }, "image/png");
    } catch (err) {
      console.error("Screenshot failed:", err);
      setScreenshotSaving(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acceptanceFile, emissionFile, diffMode, isEyedropperActive, hoverColor]);

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
      // Note: We DO NOT call cleanUpFile() here because React StrictMode 
      // unmounts and remounts immediately, which would prematurely revoke 
      // the Blob URLs while they are still in state.
      // Old files are already properly cleaned up in handleDrop/uploadAndProcess.
      
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
  // Format MM:SS for timeline
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  // Format MM:SS:FF for timecode (25 fps)
  const formatTimecode = (time: number, fps = 25) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    const frames = Math.floor((time % 1) * fps);
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}:${frames.toString().padStart(2, "0")}`;
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 pb-20">
      {/* Eyedropper Tooltip */}
      {isEyedropperActive && hoverColor && (
        <div 
          className="fixed z-50 pointer-events-none flex items-center bg-gray-900/95 text-white rounded-xl shadow-2xl border border-gray-700/50 p-2 overflow-hidden backdrop-blur-md"
          style={{ left: hoverColor.x + 20, top: hoverColor.y + 20 }}
        >
          <div 
            className="w-10 h-10 rounded-md border-2 border-white/20 shadow-inner mr-3"
            style={{ backgroundColor: hoverColor.hex }}
          ></div>
          <div className="flex flex-col font-mono text-xs pr-2">
            <span className="font-bold text-gray-100 text-sm mb-0.5 tracking-wider">{hoverColor.hex}</span>
            <span className="text-gray-400">RGB: <span className="text-gray-200">{hoverColor.r}, {hoverColor.g}, {hoverColor.b}</span></span>
          </div>
        </div>
      )}

      {/* Title Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-1">Cradle DualPlay</h2>
          <p className="text-gray-500 text-sm">
            Przeciągnij i upuść pliki wideo, aby odtworzyć je obok siebie w pełnej synchronizacji. Obsługuje formaty MP4, MOV oraz MXF.
          </p>
        </div>

        {/* ── Diff Mode Toolbar ── */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => diffMode ? deactivateDiffMode() : activateDiffMode()}
            disabled={!acceptanceFile || !emissionFile}
            title={diffMode ? "Wyłącz tryb porównania" : "Włącz tryb porównania (Diff Overlay)"}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
              diffMode
                ? "bg-red-600 hover:bg-red-700 text-white shadow-red-600/20"
                : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-600/20"
            }`}
          >
            {diffMode ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
            {diffMode ? "Diff ON" : "Diff OFF"}
            {isAnalyzing && diffMode && (
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
            )}
          </button>

          <button
            onClick={captureScreenshot}
            disabled={!acceptanceFile || !emissionFile || screenshotSaving}
            title="Zapisz screenshot do Downloads"
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold shadow-sm bg-gray-800 hover:bg-gray-900 text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CameraIcon className="w-4 h-4" />
            {screenshotSaving ? "Zapisuję…" : "Screenshot"}
          </button>
        </div>
      </div>

      {/* ── Wipe / Diff Overlay Panel (visible only in diff mode) ── */}
      {diffMode && acceptanceFile && emissionFile && (
        <div className="mb-6 bg-gray-950 rounded-2xl overflow-hidden border border-gray-800 shadow-xl">
          <div className="px-5 py-3 flex items-center justify-between border-b border-gray-800">
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold text-white">Wipe / Diff View</span>
              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                <span className="w-3 h-3 rounded-sm bg-red-600 inline-block" /> Pewna różnica
                <span className="w-3 h-3 rounded-sm bg-yellow-400 inline-block ml-2" /> Do sprawdzenia
              </span>
            </div>
            <button
              onClick={() => analyzeCurrentFrame()}
              className="text-xs px-3 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              Odśwież klatkę
            </button>
          </div>

          {/* Wipe container — canvas-based, reads directly from main video refs.
               NO extra <video> elements here → no ref conflicts → no freeze on exit. */}
          <div
            ref={wipeContainerRef}
            className="relative w-full select-none"
            style={{ background: "#000", aspectRatio: "16/9", cursor: "col-resize" }}
            onMouseDown={handleWipeMouseDown}
          >
            <canvas
              ref={wipeCanvasRef}
              className="block w-full h-full"
            />
          </div>

          {/* Wipe position slider */}
          <div className="px-5 py-3 border-t border-gray-800 flex items-center gap-4">
            <span className="text-xs text-gray-400 w-16">Pozycja:</span>
            <input
              type="range" min={0} max={100} step={0.5}
              value={wipePosition}
              onChange={(e) => setWipePosition(parseFloat(e.target.value))}
              className="flex-grow h-1.5 appearance-none bg-gray-700 rounded accent-white cursor-pointer"
            />
            <span className="text-xs text-gray-400 w-10 text-right font-mono">{wipePosition.toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* ── Diff Timestamps Panel ── */}
      {diffMode && diffTimestamps.length > 0 && (
        <div className="mb-6 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">Wykryte różnice ({diffTimestamps.length})</span>
            <span className="text-xs text-gray-400">Kliknij aby teleportować oba playery</span>
          </div>
          <div className="flex flex-wrap gap-2 p-4">
            {diffTimestamps.map((ts, i) => (
              <button
                key={i}
                onClick={() => teleportToTimestamp(ts.time)}
                title={ts.severity === "certain" ? "Pewna różnica" : "Do sprawdzenia"}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-all hover:scale-105 ${
                  ts.severity === "certain"
                    ? "bg-red-50 border-red-200 text-red-700 hover:bg-red-100"
                    : "bg-yellow-50 border-yellow-200 text-yellow-700 hover:bg-yellow-100"
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${
                  ts.severity === "certain" ? "bg-red-500" : "bg-yellow-400"
                }`} />
                {formatTimecode(ts.time)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── No-diff info (diff mode active, no differences yet) ── */}
      {diffMode && diffTimestamps.length === 0 && isAnalyzing && (
        <div className="mb-6 px-5 py-3 bg-green-50 border border-green-200 rounded-2xl text-sm text-green-700 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Analiza w toku — brak wykrytych różnic.
        </div>
      )}

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
              <h3 className="font-semibold text-green-800">Acceptance</h3>
              {acceptanceFile && (
                <p className="text-xs text-gray-500 flex items-center mt-0.5" title={acceptanceFile.name}>
                  <span className="truncate max-w-[200px]">{acceptanceFile.name}</span>
                  <span className="flex-shrink-0 ml-1.5 font-medium whitespace-nowrap">
                    • {formatFileSize(acceptanceFile.size)}
                    {accDimensions && ` • ${accDimensions.width}x${accDimensions.height}`}
                  </span>
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
                className={`w-full h-full object-contain bg-black rounded-lg ${isEyedropperActive && !isPlaying ? "cursor-crosshair" : ""}`}
                src={acceptanceFile.url}
                crossOrigin="anonymous"
                preload="auto"
                onLoadedMetadata={(e) => {
                  setAccDimensions({ width: e.currentTarget.videoWidth, height: e.currentTarget.videoHeight });
                }}
                onMouseMove={(e) => handleMouseMove(e, acceptanceVideoRef)}
                onError={() => {
                  setAcceptanceError("Nie udało się załadować strumienia wideo z serwera (np. plik wygasł w trybie DEV lub brak połączenia).");
                }}
              />
            ) : (
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center p-6 text-center text-gray-400 bg-white">
                <ArrowUpTrayIcon className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-semibold text-gray-700">Przeciągnij i upuść wideo Acceptance</p>
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
              <h3 className="font-semibold text-red-800">Emission</h3>
              {emissionFile && (
                <p className="text-xs text-gray-500 flex items-center mt-0.5" title={emissionFile.name}>
                  <span className="truncate max-w-[200px]">{emissionFile.name}</span>
                  <span className="flex-shrink-0 ml-1.5 font-medium whitespace-nowrap">
                    • {formatFileSize(emissionFile.size)}
                    {emDimensions && ` • ${emDimensions.width}x${emDimensions.height}`}
                  </span>
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
                className={`w-full h-full object-contain bg-black rounded-lg ${isEyedropperActive && !isPlaying ? "cursor-crosshair" : ""}`}
                src={emissionFile.url}
                crossOrigin="anonymous"
                preload="auto"
                onLoadedMetadata={(e) => {
                  setEmDimensions({ width: e.currentTarget.videoWidth, height: e.currentTarget.videoHeight });
                }}
                onMouseMove={(e) => handleMouseMove(e, emissionVideoRef)}
                onError={() => {
                  setEmissionError("Nie udało się załadować strumienia wideo z serwera (np. plik wygasł w trybie DEV lub brak połączenia).");
                }}
              />
            ) : (
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center p-6 text-center text-gray-400 bg-white">
                <ArrowUpTrayIcon className="w-12 h-12 text-gray-300 mb-3" />
                <p className="text-sm font-semibold text-gray-700">Przeciągnij i upuść wideo Emission</p>
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
            <div className="flex flex-col items-end w-20 flex-shrink-0">
              <span className="text-sm text-gray-700 font-mono font-medium">
                {formatTimecode(currentTime)}
              </span>
              <span className="text-[10px] text-gray-400 font-mono">
                {formatTime(currentTime)}
              </span>
            </div>
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
            <div className="flex flex-col items-start w-20 flex-shrink-0">
              <span className="text-sm text-gray-700 font-mono font-medium">
                {formatTimecode(duration)}
              </span>
              <span className="text-[10px] text-gray-400 font-mono">
                {formatTime(duration)}
              </span>
            </div>
          </div>

          {/* Navigation Control Buttons */}
          <div className="flex items-center justify-center space-x-3 flex-shrink-0">
            {/* Step Backward */}
            <button
              onClick={() => handleStep(-1)}
              disabled={!acceptanceFile && !emissionFile}
              className="w-10 h-10 flex items-center justify-center bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-gray-100"
              title="-1 Klatka"
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>

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

            {/* Step Forward */}
            <button
              onClick={() => handleStep(1)}
              disabled={!acceptanceFile && !emissionFile}
              className="w-10 h-10 flex items-center justify-center bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-gray-100"
              title="+1 Klatka"
            >
              <ChevronRightIcon className="w-5 h-5" />
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

            {/* Eyedropper Toggle */}
            <div className="w-px h-6 bg-gray-300 mx-2"></div>
            <button
              onClick={() => {
                setIsEyedropperActive(!isEyedropperActive);
                if (isEyedropperActive) setHoverColor(null);
              }}
              disabled={!acceptanceFile && !emissionFile}
              className={`w-10 h-10 flex items-center justify-center rounded-xl transition-colors disabled:opacity-40 disabled:hover:bg-transparent ${
                isEyedropperActive 
                  ? "bg-indigo-100 text-indigo-700 hover:bg-indigo-200" 
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
              title={isEyedropperActive ? "Wyłącz próbnik koloru (Kroplomierz)" : "Włącz próbnik koloru (Kroplomierz, aktywny na pauzie)"}
            >
              <EyeDropperIcon className="w-5 h-5" />
            </button>

            {/* Analyze current frame (only visible in diff mode) */}
            {diffMode && (
              <button
                onClick={() => analyzeCurrentFrame()}
                title="Analizuj bieżącą klatkę"
                className="w-10 h-10 flex items-center justify-center bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-xl transition-colors"
              >
                <EyeIcon className="w-5 h-5" />
              </button>
            )}

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
