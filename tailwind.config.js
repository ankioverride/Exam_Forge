/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#080d16',
        surface:  '#0f1622',
        surface2: '#162030',
        surface3: '#1c2940',
        border:   '#1a2d4a',
        border2:  '#244166',
        gold:     '#e8a020',
        'gold-hover': '#f0b535',
        'gold-dim': 'rgba(232,160,32,0.12)',
        ink:      '#dce5f0',
        bright:   '#f0f5fb',
        muted:    '#5c7290',
        correct:  '#22c55e',
        wrong:    '#ef4444',
        dim:      '#2d3f58',
      },
      fontFamily: {
        display: ['"Libre Baskerville"', 'Georgia', 'serif'],
        sans:    ['"Nunito Sans"', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}

