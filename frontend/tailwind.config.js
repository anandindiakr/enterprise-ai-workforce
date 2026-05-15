/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-dm-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace"],
        display: ["var(--font-syne)", "ui-sans-serif"],
      },
      colors: {
        surface: {
          DEFAULT: "#0c111d",
          2: "#111827",
          3: "#1a2332",
        },
      },
      keyframes: {
        statusPulse: {
          "0%, 100%": { opacity: "1", boxShadow: "0 0 0 0 rgba(16,185,129,0.5)" },
          "50%": { opacity: "0.8", boxShadow: "0 0 0 6px rgba(16,185,129,0)" },
        },
        wave: {
          "0%, 100%": { height: "6px" },
          "50%": { height: "22px" },
        },
        typingBounce: {
          "0%, 60%, 100%": { transform: "translateY(0)" },
          "30%": { transform: "translateY(-6px)" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        ripple: {
          "0%": { transform: "scale(1)", opacity: "0.6" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        spin: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        statusPulse: "statusPulse 2.5s ease-in-out infinite",
        wave: "wave 1.2s ease-in-out infinite",
        typingBounce: "typingBounce 1.4s ease-in-out infinite both",
        slideUp: "slideUp 0.2s ease-out",
        ripple: "ripple 2s ease-out infinite",
        spin: "spin 1s linear infinite",
      },
    },
  },
  plugins: [],
};
