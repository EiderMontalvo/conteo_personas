/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        amber: {
          DEFAULT: '#eab308',
          dark: '#ca8a04',
          soft: '#fef08a',
          border: 'rgba(234, 179, 8, .3)'
        },
        teal: {
          DEFAULT: '#0d9488',
          dark: '#0f766e',
          soft: '#ccfbf1'
        },
        green: {
          DEFAULT: '#059669',
          soft: '#d1fae5'
        },
        red: {
          DEFAULT: '#dc2626',
          soft: '#fee2e2'
        },
        purple: {
          DEFAULT: '#7c3aed',
          soft: '#ede9fe'
        },
        blue: {
          DEFAULT: '#2563eb',
          soft: '#dbeafe'
        },
        surface: {
          DEFAULT: '#ffffff',
          2: '#f8f9fb'
        },
        sidebar: '#ffffff',
        muted: '#6b7280',
        xmuted: '#9ca3af',
        body: '#f4f6f8'
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        xs: '0 1px 2px rgba(0, 0, 0, .05)',
        sm: '0 1px 4px rgba(0, 0, 0, .08), 0 1px 3px rgba(0, 0, 0, .06)',
        md: '0 4px 12px rgba(0, 0, 0, .10)',
        lg: '0 10px 30px rgba(0, 0, 0, .12)'
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '10px',
        lg: '14px',
        xl: '18px'
      }
    },
  },
  plugins: [],
}
