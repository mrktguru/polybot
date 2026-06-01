import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0b0e14",
        panel: "#141a24",
        border: "#1f2733",
        accent: "#3b82f6",
        profit: "#22c55e",
        loss: "#ef4444",
      },
    },
  },
  plugins: [],
};

export default config;
