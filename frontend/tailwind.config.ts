import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        purpos: {
          ink: "#252231",
          violet: "#7151b8",
          lilac: "#ebe3ff",
          line: "#ded8ea"
        }
      }
    }
  },
  plugins: []
};

export default config;
