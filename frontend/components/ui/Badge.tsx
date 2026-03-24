'use client';

import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
}

export function Badge({ children, className, variant = 'default', size = 'sm' }: BadgeProps) {
  const variants = {
    default: 'bg-surface-container-high text-on-surface-variant',
    primary: 'bg-primary/20 text-primary',
    secondary: 'bg-secondary/20 text-secondary',
    success: 'bg-secondary/20 text-secondary',
    warning: 'bg-tertiary/20 text-tertiary',
    error: 'bg-error/20 text-error',
    info: 'bg-primary/20 text-primary',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-label-sm',
    md: 'px-2.5 py-1 text-label-md',
  };

  return (
    <span className={cn(
      'inline-flex items-center rounded-full font-medium',
      variants[variant],
      sizes[size],
      className
    )}>
      {children}
    </span>
  );
}
