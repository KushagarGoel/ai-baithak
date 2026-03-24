'use client';

import { cn } from '@/lib/utils';
import { TextareaHTMLAttributes, forwardRef } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-label-md text-on-surface-variant mb-1.5">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          className={cn(
            'w-full bg-surface-container-highest text-on-surface rounded-lg px-4 py-3',
            'border border-transparent focus:border-b-primary focus:bg-surface-bright',
            'transition-all duration-200 placeholder:text-on-surface-variant/50',
            'resize-none',
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

Textarea.displayName = 'Textarea';

export default Textarea;
export { Textarea };
