/**
 * Tailwind for WellNest.
 *
 * preflight is OFF on purpose: the staff console and the patient portal are still styled by
 * hand-written CSS, and Tailwind's reset would strip them. Utilities and the component libraries
 * (Vengeance UI / Skiper UI) work fine without it.
 *
 * The theme maps onto the CSS custom properties in src/styles/tokens.css, so anything pulled in
 * from a component library inherits WellNest's own palette instead of shadcn's slate defaults.
 */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  corePlugins: { preflight: false },
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        sunk: "var(--bg-sunk)",
        deep: "var(--bg-deep)",
        card: "var(--card)",
        ink: {
          DEFAULT: "var(--ink)",
          soft: "var(--ink-soft)",
          muted: "var(--muted)",
          faint: "var(--faint)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          deep: "var(--accent-deep)",
          tint: "var(--accent-tint)",
          edge: "var(--accent-edge)",
        },
        gold: {
          DEFAULT: "var(--gold)",
          bright: "var(--gold-bright)",
          leaf: "var(--gold-leaf)",
          tint: "var(--gold-tint)",
        },
        alert: { DEFAULT: "var(--alert)", tint: "var(--alert-tint)" },
        ok: { DEFAULT: "var(--ok)", tint: "var(--ok-tint)" },
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        // shadcn-compatible aliases, so library components land on our palette
        background: "var(--bg)",
        foreground: "var(--ink)",
        primary: { DEFAULT: "var(--accent)", foreground: "#ffffff" },
        secondary: { DEFAULT: "var(--bg-sunk)", foreground: "var(--ink)" },
        muted: { DEFAULT: "var(--bg-sunk)", foreground: "var(--muted)" },
        border: "var(--line)",
        input: "var(--control)",
        ring: "var(--gold-bright)",
        destructive: { DEFAULT: "var(--alert)", foreground: "#ffffff" },
      },
      fontFamily: {
        serif: ["Petrona Variable", "Petrona", "Georgia", "serif"],
        sans: ["Lexend Variable", "Lexend", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        md: "var(--radius)",
        sm: "8px",
      },
      boxShadow: {
        1: "var(--shadow-1)",
        2: "var(--shadow-2)",
        3: "var(--shadow-3)",
      },
      keyframes: {
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        "marquee-y": { from: { transform: "translateY(0)" }, to: { transform: "translateY(-50%)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        marquee: "marquee var(--marquee-duration, 40s) linear infinite",
        "marquee-y": "marquee-y var(--marquee-duration, 40s) linear infinite",
        shimmer: "shimmer 1.4s infinite",
      },
    },
  },
  plugins: [],
};
