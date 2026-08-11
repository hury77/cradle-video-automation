/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          indigo: '#350F9C',
          cobalt: '#4960E6',
          purple: '#6816B0',
          magenta: '#FF00FF',
          cyan: '#00FFFF',
          charcoal: '#3E3E3E',
          smoke: '#E1E1E1',
          dark: '#0d0e15',
          'dark-card': '#161824',
          'dark-border': '#26293d',
        },
        primary: {
          50: '#eff6ff',
          500: '#4960E6',
          600: '#350F9C',
          700: '#230a6b',
        },
        slate: {
          900: '#3E3E3E',
        },
        gray: {
          900: '#3E3E3E',
        }
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
