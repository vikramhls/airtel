/** @type {import('tailwindcss').Config} */
// Dark "SYNC" theme: near-black surfaces, one glowing red accent, light text.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#E8141C", dark: "#B80F16", light: "#2A0D10", ring: "#FF3B42", glow: "#FF2A33" },
        ink: { DEFAULT: "#F4F4F5", soft: "#B4B4BB", faint: "#86868F" },
        surface: { DEFAULT: "#141416", 2: "#0F0F11", 3: "#1E1E22" },
        page: "#09090A",
        line: { DEFAULT: "#26262B", strong: "#3A3A41" },
        warn: { DEFAULT: "#FFB547", bg: "#2A1F0B", edge: "#C98A1E" },
        bad: { DEFAULT: "#FF6B6B", bg: "#2B1012" },
        good: { DEFAULT: "#4ADE80", bg: "#0E2318" },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(232,20,28,0.55), 0 0 18px rgba(255,42,51,0.35)",
        card: "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 24px rgba(0,0,0,0.35)",
      },
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "Noto Sans Devanagari", "sans-serif"] },
    },
  },
  plugins: [],
};
