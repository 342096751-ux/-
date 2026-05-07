/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        panel: 'rgb(12 12 20 / 0.85)',
        surface: 'rgb(24 24 40 / 0.6)',
        line: 'rgb(100 116 139 / 0.35)',
        accent: '#22d3ee',
        danger: '#f87171',
        safe: '#4ade80',
      },
    },
  },
  plugins: [],
};
