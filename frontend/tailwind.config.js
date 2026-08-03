/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    borderRadius: {
      none: '0',
      sm: '0.125rem',
      DEFAULT: '0.25rem',
      md: '0.375rem',
      lg: '0.5rem',
      xl: '0.75rem',
      '2xl': '1rem',
      full: '9999px',
    },
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: {
          DEFAULT: '#f7f9fb',
          low: '#f2f4f6',
          container: '#eceef0',
          high: '#e6e8ea',
          lowest: '#ffffff',
        },
        'on-surface': '#191c1e',
        'on-surface-variant': '#414750',
        outline: {
          DEFAULT: '#717781',
          variant: '#c1c7d2',
        },
        primary: {
          DEFAULT: '#00548d',
          container: '#1a6daf',
        },
        secondary: {
          DEFAULT: '#006971',
          container: '#78f1ff',
        },
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        'pathology-pink': '#F45EAC',
        'alert-yellow': '#FDCB12',
        'clinical-white': '#FFFFFF',
        'surgical-gray': '#E2E8F0',
      },
    },
  },
  plugins: [],
}
