import React from 'react';
import { DifferenceMarker } from '../../types/video';
import { 
  ChevronLeftIcon, 
  ChevronRightIcon, 
  ExclamationTriangleIcon,
  SpeakerWaveIcon,
  VideoCameraIcon 
} from '@heroicons/react/24/outline';
import { clsx } from 'clsx';

interface DifferenceNavigatorProps {
  differences: DifferenceMarker[];
  currentIndex: number;
  onPrevious: () => void;
  onNext: () => void;
  onJumpTo: (index: number) => void;
  className?: string;
}

export const DifferenceNavigator: React.FC<DifferenceNavigatorProps> = ({
  differences,
  currentIndex,
  onPrevious,
  onNext,
  onJumpTo,
  className
}) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getSeverityColor = (severity: DifferenceMarker['severity']) => {
    switch (severity) {
      case 'high':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'medium':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getTypeIcon = (type: DifferenceMarker['type']) => {
    switch (type) {
      case 'video':
        return <VideoCameraIcon className="w-4 h-4" />;
      case 'audio':
        return <SpeakerWaveIcon className="w-4 h-4" />;
      default:
        return <ExclamationTriangleIcon className="w-4 h-4" />;
    }
  };

  if (differences.length === 0) {
    return (
      <div className={clsx('bg-white rounded-lg shadow p-6', className)}>
        <div className="text-center">
          <div className="text-green-600 text-lg font-medium">
            ✓ No differences detected
          </div>
          <div className="text-gray-500 text-sm mt-2">
            The acceptance and emission videos appear to be identical
          </div>
        </div>
      </div>
    );
  }

  const currentDifference = differences[currentIndex];

  return (
    <div className={clsx('bg-white rounded-lg shadow', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">
            Differences Found ({differences.length})
          </h3>
          <div className="flex items-center space-x-2">
            <button
              onClick={onPrevious}
              disabled={currentIndex <= 0}
              className={clsx(
                'p-2 rounded-md',
                currentIndex <= 0
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              )}
            >
              <ChevronLeftIcon className="w-5 h-5" />
            </button>
            <span className="text-sm text-gray-600">
              {currentIndex + 1} of {differences.length}
            </span>
            <button
              onClick={onNext}
              disabled={currentIndex >= differences.length - 1}
              className={clsx(
                'p-2 rounded-md',
                currentIndex >= differences.length - 1
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              )}
            >
              <ChevronRightIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Current Difference Details */}
      {currentDifference && (
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-start space-x-4">
            <div className={clsx(
              'flex items-center justify-center w-10 h-10 rounded-full',
              getSeverityColor(currentDifference.severity)
            )}>
              {getTypeIcon(currentDifference.type)}
            </div>
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <h4 className="text-sm font-medium text-gray-900">
                  {currentDifference.type === 'video' ? 'Video Difference' : 'Audio Difference'}
                </h4>
                <span className={clsx(
                  'px-2 py-1 text-xs font-medium rounded-full',
                  getSeverityColor(currentDifference.severity)
                )}>
                  {currentDifference.severity} confidence
                </span>
              </div>
              <div className="text-sm text-gray-600 mt-1">
                {currentDifference.description}
              </div>
              <div className="text-sm text-gray-500 mt-1">
                Timestamp: {formatTime(currentDifference.timestamp)} • 
                Confidence: {(currentDifference.confidence * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Differences List */}
      <div className="px-6 py-4">
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {differences.map((difference, index) => (
            <div
              key={difference.id}
              onClick={() => onJumpTo(index)}
              className={clsx(
                'flex items-center space-x-3 p-3 rounded-md cursor-pointer transition-colors',
                index === currentIndex
                  ? 'bg-blue-50 border border-blue-200'
                  : 'hover:bg-gray-50 border border-transparent'
              )}
            >
              <div className={clsx(
                'flex items-center justify-center w-8 h-8 rounded-full',
                getSeverityColor(difference.severity)
              )}>
                {getTypeIcon(difference.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-900">
                    {formatTime(difference.timestamp)}
                  </span>
                  <span className={clsx(
                    'px-1.5 py-0.5 text-xs font-medium rounded',
                    getSeverityColor(difference.severity)
                  )}>
                    {difference.severity}
                  </span>
                </div>
                <div className="text-sm text-gray-600 truncate">
                  {difference.description}
                </div>
              </div>
              <div className="text-xs text-gray-500">
                {(difference.confidence * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="px-6 py-4 bg-gray-50 rounded-b-lg">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Quick navigation: Use ← → arrow keys
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => onJumpTo(0)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              First
            </button>
            <span className="text-gray-300">•</span>
            <button
              onClick={() => onJumpTo(differences.length - 1)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Last
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
