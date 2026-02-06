import React, { useState, useEffect, useRef } from 'react';
import { XMarkIcon, ChevronLeftIcon, ChevronRightIcon, EyeIcon, EyeSlashIcon, AdjustmentsHorizontalIcon } from '@heroicons/react/24/outline';

interface DifferenceInspectorProps {
    isOpen: boolean;
    onClose: () => void;
    differences: Array<{
        timestamp_seconds: number;
        difference_type: string;
        confidence: number;
    }>;
    diffFrames: Record<string, string>; // timestamp -> image_path
    videoUrls: {
        acceptance: string;
        emission: string;
    };
    metadata: {
        acceptanceName: string;
        emissionName: string;
        acceptanceDims: { width: number; height: number };
        emissionDims: { width: number; height: number };
    };
    initialTimestamp?: number | null;
}

const DifferenceInspector: React.FC<DifferenceInspectorProps> = ({
    isOpen,
    onClose,
    differences,
    diffFrames,
    videoUrls,
    metadata,
    initialTimestamp
}) => {
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [imagesLoaded, setImagesLoaded] = useState(false);
    
    // Heatmap Controls
    const [heatmapOpacity, setHeatmapOpacity] = useState(0.7);
    const [showContext, setShowContext] = useState(true);
    
    // ... refs ...
    const accVideoRef = useRef<HTMLVideoElement>(null);
    const emVideoRef = useRef<HTMLVideoElement>(null);
    const contextVideoRef = useRef<HTMLVideoElement>(null);

    // Filter unique timestamps to avoid duplicates in the navigator
    // Sorted by timestamp
    const sortedDiffs = React.useMemo(() => {
        return [...differences].sort((a, b) => a.timestamp_seconds - b.timestamp_seconds);
    }, [differences]);

    // Reset/Sync index when opened with a specific timestamp
    useEffect(() => {
        if (isOpen && initialTimestamp !== undefined && initialTimestamp !== null) {
            const idx = sortedDiffs.findIndex(d => Math.abs(d.timestamp_seconds - initialTimestamp) < 0.1);
            if (idx !== -1) {
                setSelectedIndex(idx);
            }
        }
    }, [isOpen, initialTimestamp, sortedDiffs]);

    // Effect to sync videos when index changes
    useEffect(() => {
        if (!isOpen) return;
        
        const currentDiff = sortedDiffs[selectedIndex];
        if (currentDiff) {
            const time = currentDiff.timestamp_seconds;
            
            if (accVideoRef.current) accVideoRef.current.currentTime = time;
            if (emVideoRef.current) emVideoRef.current.currentTime = time;
            if (contextVideoRef.current) contextVideoRef.current.currentTime = time;
        }
    }, [selectedIndex, isOpen, sortedDiffs]);

    if (!isOpen) return null;

    const currentDiff = sortedDiffs[selectedIndex];
    const timestamp = currentDiff ? currentDiff.timestamp_seconds : 0;
    
    // Find closest image key
    const timeKeyInt = Math.floor(timestamp).toString();
    const timeKeyFloat = timestamp.toFixed(1);
    
    let diffImagePath = diffFrames[timeKeyInt] || diffFrames[timeKeyFloat];
    
    // Fallback search if exact key missing
    if (!diffImagePath && Object.keys(diffFrames).length > 0) {
       const keys = Object.keys(diffFrames);
       const closestKey = keys.reduce((prev, curr) => 
           Math.abs(Number(curr) - timestamp) < Math.abs(Number(prev) - timestamp) ? curr : prev
       );
       if (Math.abs(Number(closestKey) - timestamp) < 1.0) {
           diffImagePath = diffFrames[closestKey];
       }
    }
    
    // Construct full URL for image
    const fullDiffUrl = diffImagePath ? `http://localhost:8001${diffImagePath}` : null;

    const formatTime = (time: number) => {
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        const ms = Math.floor((time % 1) * 100);
        return `${minutes}:${seconds.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
    };

    return (
        <div className="fixed inset-0 z-50 overflow-hidden bg-gray-900 bg-opacity-95 flex flex-col">
            {/* Header / Navigation */}
            <div className="bg-gray-800 border-b border-gray-700 p-4 flex items-center justify-between">
                <div className="flex items-center space-x-6 overflow-x-auto min-w-0 pb-2 scrollbar-thin scrollbar-thumb-gray-600">
                    <h2 className="text-white font-semibold text-lg whitespace-nowrap mr-4">
                        Difference Inspector
                    </h2>
                    
                    {/* Bubbles Navigation */}
                    <div className="flex items-center space-x-2">
                        {sortedDiffs.map((diff, idx) => (
                            <button
                                key={`${diff.timestamp_seconds}-${idx}`}
                                onClick={() => setSelectedIndex(idx)}
                                className={`
                                    w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all
                                    ${selectedIndex === idx 
                                        ? 'bg-red-600 text-white scale-110 ring-2 ring-red-400' 
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}
                                `}
                            >
                                {idx + 1}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex items-center space-x-4 pl-4 border-l border-gray-700 ml-4">
                    <div className="text-gray-400 text-sm font-mono">
                        timestamp: <span className="text-white">{formatTime(timestamp)}</span>
                    </div>
                    <button 
                        onClick={onClose}
                        className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
                    >
                        <XMarkIcon className="w-6 h-6" />
                    </button>
                </div>
            </div>

            {/* Main Content - 3 Panels */}
            <div className="flex-grow p-6 grid grid-cols-3 gap-6 h-full overflow-hidden">
                
                {/* 1. Acceptance */}
                <div className="flex flex-col bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
                    <div className="p-3 bg-gray-900 border-b border-gray-700 flex justify-between items-center">
                        <span className="text-gray-300 font-medium text-sm">Acceptance (Reference)</span>
                        <span className="text-xs text-gray-500">{metadata.acceptanceDims.width}x{metadata.acceptanceDims.height}</span>
                    </div>
                    <div className="flex-grow relative bg-black flex items-center justify-center group">
                        <video 
                            ref={accVideoRef}
                            src={videoUrls.acceptance}
                            className="max-w-full max-h-full object-contain"
                            muted
                        />
                        <div className="absolute bottom-4 left-4 text-xs font-mono text-white bg-black/50 px-2 py-1 rounded">
                            {metadata.acceptanceName}
                        </div>
                    </div>
                </div>

                {/* 2. Emission */}
                <div className="flex flex-col bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
                    <div className="p-3 bg-gray-900 border-b border-gray-700 flex justify-between items-center">
                        <span className="text-gray-300 font-medium text-sm">Emission (Actual)</span>
                        <span className="text-xs text-gray-500">{metadata.emissionDims.width}x{metadata.emissionDims.height}</span>
                    </div>
                    <div className="flex-grow relative bg-black flex items-center justify-center">
                        <video 
                            ref={emVideoRef}
                            src={videoUrls.emission}
                            className="max-w-full max-h-full object-contain"
                            muted
                        />
                         <div className="absolute bottom-4 left-4 text-xs font-mono text-white bg-black/50 px-2 py-1 rounded">
                            {metadata.emissionName}
                        </div>
                    </div>
                </div>

                {/* 3. Difference (Composite View) */}
                <div className="flex flex-col bg-gray-800 rounded-xl overflow-hidden border border-red-900/30">
                    <div className="p-3 bg-gray-900 border-b border-gray-700 flex justify-between items-center">
                        <span className="text-red-400 font-medium text-sm">Difference Layer</span>
                        <div className="flex items-center space-x-2">
                             <div className="flex items-center space-x-1 bg-gray-800 rounded px-2 py-0.5">
                                <span className="text-[10px] text-gray-400">OPACITY</span>
                                <input 
                                    type="range" 
                                    min="0" max="1" step="0.1" 
                                    value={heatmapOpacity}
                                    onChange={(e) => setHeatmapOpacity(Number(e.target.value))}
                                    className="w-16 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-red-500"
                                />
                             </div>
                             <button
                                onClick={() => setShowContext(!showContext)}
                                className={`p-1 rounded transition-colors ${showContext ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:text-gray-300'}`}
                                title={showContext ? "Hide Context (Black BG)" : "Show Context (Video)"}
                             >
                                {showContext ? <EyeIcon className="w-4 h-4" /> : <EyeSlashIcon className="w-4 h-4" />}
                             </button>
                        </div>
                    </div>
                    <div className="flex-grow relative bg-black flex items-center justify-center overflow-hidden">
                        {/* Layer 1: Context Video (Underlay) */}
                        <div className={`absolute inset-0 flex items-center justify-center transition-opacity duration-300 ${showContext ? 'opacity-100' : 'opacity-0'}`}>
                             <video 
                                ref={contextVideoRef}
                                src={videoUrls.acceptance}
                                className="max-w-full max-h-full object-contain filter grayscale-[50%] brightness-75" // Dimmed specifically for better contrast
                                muted
                            />
                        </div>

                        {/* Layer 2: Heatmap Mask (Overlay) */}
                        <div className="relative z-10 w-full h-full flex items-center justify-center pointer-events-none">
                            {fullDiffUrl ? (
                                <img 
                                    src={fullDiffUrl} 
                                    alt="Difference Mask" 
                                    className="max-w-full max-h-full object-contain"
                                    style={{ 
                                        mixBlendMode: 'screen', // Magic: Black becomes transparent, Red stays
                                        opacity: heatmapOpacity 
                                    }}
                                />
                            ) : (
                                <div className="text-gray-500 text-sm flex flex-col items-center">
                                    <span>No difference mask</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

            </div>

            {/* Footer Controls */}
            <div className="bg-gray-800 border-t border-gray-700 p-4 flex justify-center pb-8">
                 <div className="flex items-center space-x-4">
                    <button 
                        onClick={() => setSelectedIndex(Math.max(0, selectedIndex - 1))}
                        disabled={selectedIndex === 0}
                        className="px-4 py-2 bg-gray-700 rounded-lg text-white hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                    >
                        <ChevronLeftIcon className="w-5 h-5 mr-1" /> Prev Difference
                    </button>
                    <span className="text-gray-400 text-sm">
                        {selectedIndex + 1} / {sortedDiffs.length}
                    </span>
                    <button 
                        onClick={() => setSelectedIndex(Math.min(sortedDiffs.length - 1, selectedIndex + 1))}
                        disabled={selectedIndex === sortedDiffs.length - 1}
                        className="px-4 py-2 bg-gray-700 rounded-lg text-white hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                    >
                        Next Difference <ChevronRightIcon className="w-5 h-5 ml-1" />
                    </button>
                 </div>
            </div>
        </div>
    );
};

export default DifferenceInspector;
