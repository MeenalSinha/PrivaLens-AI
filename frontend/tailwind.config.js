/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0A0E13",
          surface: "#111820",
          elevated: "#19222C",
          hover: "#212B37",
        },
        border: {
          DEFAULT: "#26313D",
          light: "#34424F",
        },
        text: {
          primary: "#E7EDF3",
          secondary: "#9CACBB",
          muted: "#7E8A9A",
          disabled: "#4A5563",
        },
        accent: {
          cyan: "#3FD6C7",
          cyanDim: "#1F6B63",
        },
        risk: {
          low: "#3FD6C7",
          moderate: "#E8B339",
          high: "#E8763C",
          critical: "#E24C4C",
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(63,214,199,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(63,214,199,0.045) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "36px 36px",
      },
    },
  },
  plugins: [],
};
