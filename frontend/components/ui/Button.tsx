'use client';

import { cn } from '@/lib/utils';
import { ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, children, disabled, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50 disabled:cursor-not-allowed';

    const variants = {
      primary: 'bg-primary/90 text-on-primary hover:bg-primary shadow-glow-primary backdrop-blur-sm',
      secondary: 'bg-surface-container-high text-on-surface hover:bg-surface-container-highest border border-outline-variant/50 hover:border-outline/60 shadow-sm',
      tertiary: 'bg-tertiary/90 text-white hover:bg-tertiary shadow-sm',
      ghost: 'bg-transparent text-on-surface hover:bg-surface-container-high/50 border border-outline-variant/30',
      danger: 'bg-error/10 text-error hover:bg-error/20 border border-error/30 hover:border-error/50',
    };

    const sizes = {
      sm: 'px-3 py-1.5 text-label-md gap-1.5',
      md: 'px-4 py-2 text-body-md gap-2',
      lg: 'px-6 py-3 text-body-lg gap-2.5',
    };

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;
export { Button };
