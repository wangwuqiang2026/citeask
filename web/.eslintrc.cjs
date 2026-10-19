/* ESLint 8 flat-free config (the repository already ships .eslintrc-style tooling). */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended"],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-hooks", "react-refresh"],
  ignorePatterns: [
    "node_modules",
    "dist",
    "vite.config.ts",
    "tailwind.config.ts",
    "postcss.config.cjs",
    ".eslintrc.cjs",
  ],
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    // Fast refresh is a dev-server nicety; the rule cannot see through our
    // component files and would make `--max-warnings 0` unusable.
    "react-refresh/only-export-components": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "@typescript-eslint/no-explicit-any": "off",
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
};
