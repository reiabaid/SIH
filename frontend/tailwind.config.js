/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-dark': '#0b0f17',
        'bg-panel': '#131a26',
        'bg-card': '#182232',
      }
    },
  },
  plugins: [],
}
