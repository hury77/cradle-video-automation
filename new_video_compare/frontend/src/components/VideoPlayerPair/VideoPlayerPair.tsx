import React, { useEffect, useRef, useState } from 'react';
import videojs from 'video.js';
import 'video.js/dist/video-js.css';
import '@videojs/themes/dist/sea/index.css';
import { VideoPlayerState, SyncedPlayback } from '../../types/video';
import { PlayIcon, PauseIcon, SpeakerWaveIcon, SpeakerXMarkIcon } from '@heroicons/react/24/solid';
import { clsx } from 'clsx';

interface VideoPlayerPairProps {
  acceptanceVideoUrl?: string;
  emissionVideoUrl?: string;
  onTimeUpdate?: (player: 'acceptance' | 'emission', currentTime: number) => void;
  syncedPlayback?: SyncedPlayback;
  className?: string;
}

export const VideoPlayerPair: React.FC<VideoPlayerPairProps> = ({
  acceptanceVideoUrl,
  emissionVideoUrl,
  onTimeUpdate,
  syncedPlayback,
  className
}) => {
  const acceptanceVideoRef = useRef<HTMLVideoElement>(null);
  const emissionVideoRef = useRef<HTMLVideoElement>(null);
  const acceptancePlayerRef = useRef<any>(null);
  const emissionPlayerRef = useRef<any>(null);

  const [acceptanceState, setAcceptanceState] = useState<VideoPlayerState>({
    currentTime: 0,
    duration: 0,
    playing: false,
    volume: 1,
    muted: false
  });

  const [emissionState, setEmissionState] = useState<VideoPlayerState>({
    currentTime: 0,
    duration: 0,
    playing: false,
    volume: 1,
    muted: false
  });

  // Initialize Video.js players
  useEffect(() => {
    if (acceptanceVideoRef.current && acceptanceVideoUrl) {
      acceptancePlayerRef.current = videojs(acceptanceVideoRef.current, {
        controls: true,
        responsive: true,
        fluid: true,
        sources: [{
          src: acceptanceVideoUrl,
          type: 'video/mp4'
        }]
      });

      // Event listeners for acceptance player
      acceptancePlayerRef.current.on('loadedmetadata', () => {
        setAcceptanceState(prev => ({
          ...prev,
          duration: acceptancePlayerRef.current.duration()
        }));
      });

      acceptancePlayerRef.current.on('timeupdate', () => {
        const currentTime = acceptancePlayerRef.current.currentTime();
        setAcceptanceState(prev => ({
          ...prev,
          currentTime
        }));
        
        if (onTimeUpdate) {
          onTimeUpdate('acceptance', currentTime);
        }
      });

      acceptancePlayerRef.current.on('play', () => {
        setAcceptanceState(prev => ({ ...prev, playing: true }));
        
        // Sync emission player if enabled
        if (syncedPlayback?.syncEnabled && emissionPlayerRef.current) {
          emissionPlayerRef.current.play();
        }
      });

      acceptancePlayerRef.current.on('pause', () => {
        setAcceptanceState(prev => ({ ...prev, playing: false }));
        
        // Sync emission player if enabled
        if (syncedPlayback?.syncEnabled && emissionPlayerRef.current) {
          emissionPlayerRef.current.pause();
        }
      });

      acceptancePlayerRef.current.on('volumechange', () => {
        setAcceptanceState(prev => ({
          ...prev,
          volume: acceptancePlayerRef.current.volume(),
          muted: acceptancePlayerRef.current.muted()
        }));
      });
    }

    return () => {
      if (acceptancePlayerRef.current) {
        acceptancePlayerRef.current.dispose();
      }
    };
  }, [acceptanceVideoUrl, syncedPlayback, onTimeUpdate]);

  // Initialize emission player
  useEffect(() => {
    if (emissionVideoRef.current && emissionVideoUrl) {
      emissionPlayerRef.current = videojs(emissionVideoRef.current, {
        controls: true,
        responsive: true,
        fluid: true,
        sources: [{
          src: emissionVideoUrl,
          type: 'video/mp4'
        }]
      });

      // Event listeners for emission player
      emissionPlayerRef.current.on('loadedmetadata', () => {
        setEmissionState(prev => ({
          ...prev,
          duration: emissionPlayerRef.current.duration()
        }));
      });

      emissionPlayerRef.current.on('timeupdate', () => {
        const currentTime = emissionPlayerRef.current.currentTime();
        setEmissionState(prev => ({
          ...prev,
          currentTime
        }));
        
        if (onTimeUpdate) {
          onTimeUpdate('emission', currentTime);
        }
      });

      emissionPlayerRef.current.on('play', () => {
        setEmissionState(prev => ({ ...prev, playing: true }));
        
        // Sync acceptance player if enabled and emission is master
        if (syncedPlayback?.syncEnabled && syncedPlayback.masterPlayer === 'emission' && acceptancePlayerRef.current) {
          acceptancePlayerRef.current.play();
        }
      });

      emissionPlayerRef.current.on('pause', () => {
        setEmissionState(prev => ({ ...prev, playing: false }));
        
        // Sync acceptance player if enabled and emission is master
        if (syncedPlayback?.syncEnabled && syncedPlayback.masterPlayer === 'emission' && acceptancePlayerRef.current) {
          acceptancePlayerRef.current.pause();
        }
      });

      emissionPlayerRef.current.on('volumechange', () => {
        setEmissionState(prev => ({
          ...prev,
          volume: emissionPlayerRef.current.volume(),
          muted: emissionPlayerRef.current.muted()
        }));
      });
    }

    return () => {
      if (emissionPlayerRef.current) {
        emissionPlayerRef.current.dispose();
      }
    };
  }, [emissionVideoUrl, syncedPlayback, onTimeUpdate]);


  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={clsx('grid grid-cols-1 lg:grid-cols-2 gap-6', className)}>
      {/* Acceptance Video Player */}
      <div className="bg-gray-900 rounded-lg overflow-hidden">
        <div className="bg-green-600 text-white px-4 py-2 font-medium">
          Acceptance Video
        </div>
        <div className="aspect-video bg-black">
          {acceptanceVideoUrl ? (
            <video
              ref={acceptanceVideoRef}
              className="video-js vjs-theme-sea w-full h-full"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              No acceptance video loaded
            </div>
          )}
        </div>
        <div className="bg-gray-800 text-white px-4 py-2 flex items-center justify-between text-sm">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => {
                if (acceptanceState.playing) {
                  acceptancePlayerRef.current?.pause();
                } else {
                  acceptancePlayerRef.current?.play();
                }
              }}
              className="p-1 hover:bg-gray-700 rounded"
            >
              {acceptanceState.playing ? (
                <PauseIcon className="w-5 h-5" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={() => {
                const newMuted = !acceptanceState.muted;
                acceptancePlayerRef.current?.muted(newMuted);
              }}
              className="p-1 hover:bg-gray-700 rounded"
            >
              {acceptanceState.muted ? (
                <SpeakerXMarkIcon className="w-5 h-5" />
              ) : (
                <SpeakerWaveIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          <div>
            {formatTime(acceptanceState.currentTime)} / {formatTime(acceptanceState.duration)}
          </div>
        </div>
      </div>

      {/* Emission Video Player */}
      <div className="bg-gray-900 rounded-lg overflow-hidden">
        <div className="bg-red-600 text-white px-4 py-2 font-medium">
          Emission Video
        </div>
        <div className="aspect-video bg-black">
          {emissionVideoUrl ? (
            <video
              ref={emissionVideoRef}
              className="video-js vjs-theme-sea w-full h-full"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              No emission video loaded
            </div>
          )}
        </div>
        <div className="bg-gray-800 text-white px-4 py-2 flex items-center justify-between text-sm">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => {
                if (emissionState.playing) {
                  emissionPlayerRef.current?.pause();
                } else {
                  emissionPlayerRef.current?.play();
                }
              }}
              className="p-1 hover:bg-gray-700 rounded"
            >
              {emissionState.playing ? (
                <PauseIcon className="w-5 h-5" />
              ) : (
                <PlayIcon className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={() => {
                const newMuted = !emissionState.muted;
                emissionPlayerRef.current?.muted(newMuted);
              }}
              className="p-1 hover:bg-gray-700 rounded"
            >
              {emissionState.muted ? (
                <SpeakerXMarkIcon className="w-5 h-5" />
              ) : (
                <SpeakerWaveIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          <div>
            {formatTime(emissionState.currentTime)} / {formatTime(emissionState.duration)}
          </div>
        </div>
      </div>
    </div>
  );
};
