/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        emerald: {
          600: '#059669',
        },
        amber: {
          500: '#F59E0B',
        },
        rose: {
          600: '#E11D48',
        },
        indigo: {
          600: '#4F46E5',
        },
        sky: {
          600: '#0284C7',
        }
      }
    },
  },
  plugins: [],
}
