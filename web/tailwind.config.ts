import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

/**
 * Design tokens of the SPA (MODIFICATIONS §5.25). Values are HSL triplets so
 * opacity modifiers (`bg-panel/60`) work; the raw hex values live in the plan:
 * canvas #F6F7F9 / panel #FFF / border #E5E7EB / text #111827 / muted #4B5563 /
 * accent #4F46E5, dark: #0B0D12 / #12151C / #242A36 / #E7E9EE / #818CF8.
 */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "hsl(var(--canvas))",
        panel: "hsl(var(--panel))",
        elevated: "hsl(var(--elevated))",
        border: "hsl(var(--border))",
        input: "hsl(var(--border))",
        ring: "hsl(var(--ring))",
        fg: "hsl(var(--fg))",
        muted: "hsl(var(--muted))",
        subtle: "hsl(var(--subtle))",
        accent: {
          DEFAULT: "hsl(var(--accent))",
          hover: "hsl(var(--accent-hover))",
          soft: "hsl(var(--accent-soft))",
          fg: "hsl(var(--accent-fg))",
        },
        danger: "hsl(var(--danger))",
        success: "hsl(var(--success))",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Noto Sans CJK SC",
          "Source Han Sans SC",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Cascadia Code",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["12px", "16px"],
        xs: ["12px", "18px"],
        sm: ["13px", "20px"],
        base: ["14px", "22px"],
        md: ["15px", "24px"],
        lg: ["20px", "28px"],
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "14px",
      },
      spacing: {
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
      },
      boxShadow: {
        pop: "0 8px 30px rgba(17, 24, 39, 0.12)",
        composer: "0 4px 20px rgba(17, 24, 39, 0.08)",
      },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.2, 0, 0, 1)",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
