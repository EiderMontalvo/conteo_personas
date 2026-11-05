/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)' },
        line: { DEFAULT: 'var(--border)', strong: 'var(--border-strong)' },
        fg: { DEFAULT: 'var(--text)', 2: 'var(--text-2)', 3: 'var(--text-3)' },
        ink: { DEFAULT: 'var(--ink)', 2: 'var(--ink-2)', fg: 'var(--ink-fg)', muted: 'var(--ink-muted)' },
        accent: { DEFAULT: 'var(--accent)', strong: 'var(--accent-strong)', soft: 'var(--accent-soft)' },
        'on-accent': 'var(--on-accent)',
        hover: 'var(--hover)',
        track: 'var(--track)',
        out: 'var(--series-out)',
        ok: { DEFAULT: 'var(--ok)', soft: 'var(--ok-soft)' },
        warn: { DEFAULT: 'var(--warn)', soft: 'var(--warn-soft)' },
        danger: { DEFAULT: 'var(--danger)', soft: 'var(--danger-soft)' },
      },
      fontFamily: {
        sans: ['"Archivo Variable"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
      },
      boxShadow: {
        float: '0 18px 44px -10px rgba(0, 0, 0, 0.7), 0 2px 8px rgba(0, 0, 0, 0.4)',
      },
    },
  },
  plugins: [],
}
