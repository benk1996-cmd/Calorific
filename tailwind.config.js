const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;

/** Colours come from CSS variables (src/index.css) so light/dark switch in one place. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: c("bg"), card: c("card"), ink: c("ink"), ink2: c("ink-2"), muted: c("muted"), line: c("line"),
        brand: c("brand"), "brand-ink": c("brand-ink"), "brand-soft": c("brand-soft"),
        protein: c("protein"), carbs: c("carbs"), fat: c("fat"),
        warn: c("warn"), "warn-soft": c("warn-soft"), danger: c("danger"), "danger-soft": c("danger-soft"),
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgb(var(--shadow) / 0.05), 0 6px 20px rgb(var(--shadow) / 0.05)",
        float: "0 8px 30px rgb(var(--shadow) / 0.18)",
      },
      keyframes: {
        "sheet-up": { from: { transform: "translateY(24px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "toast-in": { from: { transform: "translateY(16px)", opacity: "0" }, to: { transform: "none", opacity: "1" } },
        shrink: { from: { transform: "scaleX(1)" }, to: { transform: "scaleX(0)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "sheet-up": "sheet-up .22s cubic-bezier(.2,.8,.2,1)",
        "fade-in": "fade-in .18s ease-out",
        "toast-in": "toast-in .25s cubic-bezier(.2,.8,.2,1)",
        shrink: "shrink 10s linear forwards",
      },
    },
  },
  plugins: [],
};
