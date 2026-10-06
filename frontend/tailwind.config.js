/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#F9F5F0",
        beige: "#F2EAD3",
        amber: {
          DEFAULT: "#F4991A",
          light: "#FDECC8",
          dark: "#D4820E",
        },
        forest: {
          DEFAULT: "#344F1F",
          light: "#4A6B2A",
          muted: "#6B8A4E",
        },
        "red-soft": "#E74C3C",
        "green-soft": "#27AE60",
        "blue-soft": "#2563EB",
        "gray-muted": "#64748B",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        sinhala: ["Noto Sans Sinhala", "sans-serif"],
      },
      animation: {
        "pulse-mic": "pulse-mic 1.5s ease-in-out infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.25s ease-out",
        "bar-fill": "bar-fill 0.8s ease-out forwards",
        "recording-ring": "recording-ring 1.2s ease-in-out infinite alternate",
        spin: "spin 1s linear infinite",
      },
      keyframes: {
        "pulse-mic": {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.15)" },
        },
        "slide-up": {
          "0%": { transform: "translateY(16px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "bar-fill": {
          "0%": { width: "0%" },
          "100%": { width: "var(--bar-width, 100%)" },
        },
        "recording-ring": {
          "0%": { opacity: "0.4", transform: "scale(1)" },
          "100%": { opacity: "0.8", transform: "scale(1.3)" },
        },
      },
      boxShadow: {
        card: "0 2px 12px rgba(52,79,31,0.08)",
        "card-hover": "0 6px 24px rgba(52,79,31,0.14)",
      },
    },
  },
  plugins: [],
};
