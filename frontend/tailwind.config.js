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
        background: '#0b0e14',
        surface: {
          DEFAULT: '#0b0e14',
          dim: '#0b0e14',
          bright: '#282c36',
          tint: 'rgba(129, 233, 255, 0.05)',
        },
        'surface-container': {
          lowest: '#000000',
          low: '#10131a',
          DEFAULT: '#161a21',
          high: '#1c2028',
          highest: '#22262f',
        },
        primary: {
          DEFAULT: '#81e9ff',
          dim: '#00d1ee',
          container: '#00e0ff',
          fixed: '#00e0ff',
          'fixed-dim': '#00d1ee',
        },
        secondary: {
          DEFAULT: '#3fff8b',
          dim: '#24f07e',
          container: '#006d35',
          fixed: '#3fff8b',
          'fixed-dim': '#24f07e',
        },
        tertiary: {
          DEFAULT: '#a68cff',
          dim: '#7e51ff',
          container: '#7c4dff',
          fixed: '#b8a3ff',
          'fixed-dim': '#ab93ff',
        },
        error: {
          DEFAULT: '#ff716c',
          dim: '#d7383b',
          container: '#9f0519',
        },
        outline: {
          DEFAULT: '#73757d',
          variant: '#45484f',
        },
        'on-background': '#ecedf6',
        'on-surface': '#ecedf6',
        'on-surface-variant': '#a9abb3',
        'on-primary': '#005561',
        'on-secondary': '#005d2c',
        'on-error': '#490006',
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
        'ambient': '0 20px 40px rgba(0, 0, 0, 0.4), 0 0 10px rgba(129, 233, 255, 0.05)',
        'glow-primary': '0 0 20px rgba(129, 233, 255, 0.3)',
        'glow-secondary': '0 0 20px rgba(63, 255, 139, 0.3)',
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
          '0%': { boxShadow: '0 0 5px rgba(129, 233, 255, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(129, 233, 255, 0.4)' },
        },
      },
    },
  },
  plugins: [],
};
