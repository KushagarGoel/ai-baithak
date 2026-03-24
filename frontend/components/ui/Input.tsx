'use client';

import { cn } from '@/lib/utils';
import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-label-md text-on-surface-variant mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full bg-surface-container-highest text-on-surface rounded-lg px-4 py-2.5',
            'border border-transparent focus:border-b-primary focus:bg-surface-bright',
            'transition-all duration-200 placeholder:text-on-surface-variant/50',
            error && 'border-error',
            className
          )}
          {...props}
        />
        {error && (
          <p className="mt-1 text-label-sm text-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
export { Input };
