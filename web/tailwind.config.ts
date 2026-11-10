import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2421",
        paper: "#faf7f0",
        sage: "#5b7f68",
        clay: "#b5654f",
      },
    },
  },
  plugins: [],
};

export default config;
