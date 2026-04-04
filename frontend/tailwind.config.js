/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--background) / <alpha-value>)',
        surface: {
          DEFAULT: 'rgb(var(--surface) / <alpha-value>)',
          dim: 'rgb(var(--surface-dim) / <alpha-value>)',
          bright: 'rgb(var(--surface-bright) / <alpha-value>)',
          tint: 'rgb(var(--primary) / 0.05)',
        },
        'surface-container': {
          lowest: 'rgb(var(--surface-container-lowest) / <alpha-value>)',
          low: 'rgb(var(--surface-container-low) / <alpha-value>)',
          DEFAULT: 'rgb(var(--surface-container) / <alpha-value>)',
          high: 'rgb(var(--surface-container-high) / <alpha-value>)',
          highest: 'rgb(var(--surface-container-highest) / <alpha-value>)',
        },
        primary: {
          DEFAULT: 'rgb(var(--primary) / <alpha-value>)',
          dim: 'rgb(var(--primary-dim) / <alpha-value>)',
          container: 'rgb(var(--primary-container) / <alpha-value>)',
          fixed: 'rgb(var(--primary-fixed) / <alpha-value>)',
          'fixed-dim': 'rgb(var(--primary-fixed-dim) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'rgb(var(--secondary) / <alpha-value>)',
          dim: 'rgb(var(--secondary-dim) / <alpha-value>)',
          container: 'rgb(var(--secondary-container) / <alpha-value>)',
          fixed: 'rgb(var(--secondary-fixed) / <alpha-value>)',
          'fixed-dim': 'rgb(var(--secondary-fixed-dim) / <alpha-value>)',
        },
        tertiary: {
          DEFAULT: 'rgb(var(--tertiary) / <alpha-value>)',
          dim: 'rgb(var(--tertiary-dim) / <alpha-value>)',
          container: 'rgb(var(--tertiary-container) / <alpha-value>)',
          fixed: 'rgb(var(--tertiary-fixed) / <alpha-value>)',
          'fixed-dim': 'rgb(var(--tertiary-fixed-dim) / <alpha-value>)',
        },
        error: {
          DEFAULT: 'rgb(var(--error) / <alpha-value>)',
          dim: 'rgb(var(--error-dim) / <alpha-value>)',
          container: 'rgb(var(--error-container) / <alpha-value>)',
        },
        outline: {
          DEFAULT: 'rgb(var(--outline) / <alpha-value>)',
          variant: 'rgb(var(--outline-variant) / <alpha-value>)',
        },
        'on-background': 'rgb(var(--on-background) / <alpha-value>)',
        'on-surface': 'rgb(var(--on-surface) / <alpha-value>)',
        'on-surface-variant': 'rgb(var(--on-surface-variant) / <alpha-value>)',
        'on-primary': 'rgb(var(--on-primary) / <alpha-value>)',
        'on-secondary': 'rgb(var(--on-secondary) / <alpha-value>)',
        'on-error': 'rgb(var(--on-error) / <alpha-value>)',
        success: {
          DEFAULT: 'rgb(var(--success) / <alpha-value>)',
          container: 'rgb(var(--success-container) / <alpha-value>)',
        },
        warning: {
          DEFAULT: 'rgb(var(--warning) / <alpha-value>)',
          container: 'rgb(var(--warning-container) / <alpha-value>)',
        },
        info: {
          DEFAULT: 'rgb(var(--info) / <alpha-value>)',
          container: 'rgb(var(--info-container) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'display-lg': ['3.5rem', { lineHeight: '1.1', fontWeight: '700' }],
        'display-md': ['2.75rem', { lineHeight: '1.15', fontWeight: '700' }],
        'headline-lg': ['2rem', { lineHeight: '1.25', fontWeight: '600' }],
        'headline-md': ['1.5rem', { lineHeight: '1.3', fontWeight: '600' }],
        'headline-sm': ['1.25rem', { lineHeight: '1.4', fontWeight: '600' }],
        'title-lg': ['1.125rem', { lineHeight: '1.5', fontWeight: '500' }],
        'title-md': ['1rem', { lineHeight: '1.5', fontWeight: '500' }],
        'body-lg': ['1rem', { lineHeight: '1.6', fontWeight: '400' }],
        'body-md': ['0.875rem', { lineHeight: '1.6', fontWeight: '400' }],
        'label-lg': ['0.875rem', { lineHeight: '1.4', fontWeight: '500' }],
        'label-md': ['0.75rem', { lineHeight: '1.4', fontWeight: '500' }],
        'label-sm': ['0.625rem', { lineHeight: '1.4', fontWeight: '500', letterSpacing: '0.02em' }],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '30': '7.5rem',
      },
      boxShadow: {
        'ambient': 'var(--shadow-ambient)',
        'glow-primary': 'var(--shadow-glow-primary)',
        'glow-secondary': 'var(--shadow-glow-secondary)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: 'var(--shadow-glow-primary-subtle)' },
          '100%': { boxShadow: 'var(--shadow-glow-primary)' },
        },
      },
    },
  },
  plugins: [],
};
