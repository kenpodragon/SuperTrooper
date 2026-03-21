/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/popup/**/*.{tsx,ts,html}"],
  theme: {
    extend: {
      colors: {
        st: {
          bg: "#1a1a2e",
          surface: "#16213e",
          border: "#1f3460",
          text: "#e0e0e0",
          muted: "#8899aa",
          green: "#00FF41",
          "green-dim": "#00cc33",
          red: "#ff4444",
        },
      },
    },
  },
  plugins: [],
};
