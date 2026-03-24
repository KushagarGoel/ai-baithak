'use client';

import { cn } from '@/lib/utils';

interface ProgressRingProps {
  progress: number; // 0 to 1
  size?: number;
  strokeWidth?: number;
  className?: string;
  showPercentage?: boolean;
  color?: 'primary' | 'secondary' | 'tertiary';
}

export function ProgressRing({
  progress,
  size = 60,
  strokeWidth = 4,
  className,
  showPercentage = true,
  color = 'primary',
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - Math.min(progress, 1) * circumference;

  const colors = {
    primary: 'stroke-primary',
    secondary: 'stroke-secondary',
    tertiary: 'stroke-tertiary',
  };

  const glowColors = {
    primary: 'drop-shadow-[0_0_4px_rgba(129,233,255,0.5)]',
    secondary: 'drop-shadow-[0_0_4px_rgba(63,255,139,0.5)]',
    tertiary: 'drop-shadow-[0_0_4px_rgba(166,140,255,0.5)]',
  };

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-surface-container-high"
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={cn(colors[color], glowColors[color], 'transition-all duration-500')}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      {showPercentage && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-label-md font-medium text-on-surface">
            {Math.round(progress * 100)}%
          </span>
        </div>
      )}
    </div>
  );
}
