import { fileURLToPath, URL } from "node:url";

import { transformAsync } from "@babel/core";
import presetReact from "@babel/preset-react";
import presetTypeScript from "@babel/preset-typescript";
import react from "@vitejs/plugin-react";

/**
 * Shared Vite options, used by `scripts/build.mjs`, `scripts/dev.mjs` and
 * `scripts/preview.mjs`.
 *
 * They are passed to Vite's JS API with `configFile: false` instead of living in
 * `vite.config.ts`: Vite 5 bundles *any* config file with esbuild, and esbuild's
 * service cannot start in this repository's Windows sandbox (child processes may
 * not use pipes → "spawn EPERM"). The transform chain is therefore entirely
 * in-process: `@babel/preset-typescript` removes the types, the React plugin
 * handles JSX/HMR, terser minifies. The same script runs unchanged in a normal
 * terminal — nothing here is sandbox-only behaviour.
 */
const sourceRoot = fileURLToPath(new URL("../src", import.meta.url));

/**
 * Strip TypeScript types and compile JSX.
 *
 * `@vitejs/plugin-react` v4 leaves JSX to esbuild in production builds (Babel is
 * only used for fast refresh during development), so with esbuild disabled the
 * JSX transform has to happen here. Order: types first, then JSX.
 */
function babelTypeScript() {
  return {
    name: "citeask:babel-typescript",
    enforce: "pre",
    async transform(code, id) {
      const file = id.split("?")[0];
      // Vite uses forward slashes for module ids on every platform.
      const normalized = file.replaceAll("\\", "/");
      const root = sourceRoot.replaceAll("\\", "/");
      // Only our own TS/TSX sources: Vite emits virtual modules (e.g.
      // "\0vite/modulepreload-polyfill.js") that must not go through Babel TS.
      if (!normalized.startsWith(root)) return null;
      if (!/\.tsx?$/.test(normalized)) return null;

      const result = await transformAsync(code, {
        filename: file,
        babelrc: false,
        configFile: false,
        sourceMaps: true,
        presets: [
          [presetTypeScript, {}],
          [presetReact, { runtime: "automatic", development: false }],
        ],
      });
      if (!result?.code) return null;
      return { code: result.code, map: result.map };
    },
  };
}

/**
 * Re-assert `esbuild: false`. `@vitejs/plugin-react` sets `esbuild.jsx` in its
 * own `config` hook, which would turn the option back into an object and make
 * Vite spawn the esbuild service (impossible in the sandbox). Post-enforced so
 * this hook runs last and wins.
 */
function forceNoEsbuild() {
  return {
    name: "citeask:no-esbuild",
    enforce: "post",
    config: () => ({ esbuild: false }),
  };
}

/**
 * Replace the two `define` patterns Vite would otherwise rewrite with esbuild.
 *
 * `vite:define` calls `esbuild.transform` unconditionally (even with
 * `esbuild: false`), and the esbuild service cannot start in the sandbox. A pre
 * plugin replaces the literals first, so Vite's pattern no longer matches and
 * the esbuild call never happens. It is a plain literal replacement, which is
 * what `define` does for these two identifiers anyway.
 */
function defineWorkaround() {
  let env = "production";
  // The mock switch stays usable: `VITE_USE_MOCK=1 npm run build` compiles it in.
  const mockFlag = process.env.VITE_USE_MOCK ?? "0";
  return {
    name: "citeask:define-workaround",
    enforce: "pre",
    configResolved(config) {
      env = config.mode === "production" ? "production" : "development";
    },
    transform(code, id) {
      if (id.startsWith("\0")) return null;
      if (!code.includes("process.env.NODE_ENV") && !code.includes("import.meta.env")) {
        return null;
      }
      const next = code
        .split("process.env.NODE_ENV")
        .join(JSON.stringify(env))
        .split("import.meta.env.VITE_USE_MOCK")
        .join(JSON.stringify(mockFlag))
        .split("import.meta.env")
        .join("({})");
      if (next === code) return null;
      return { code: next, map: null };
    },
  };
}

export const viteConfig = {
  base: "/",
  plugins: [defineWorkaround(), babelTypeScript(), react(), forceNoEsbuild()],
  // Transforms come from the plugins above; nothing may spawn esbuild.
  esbuild: false,
  resolve: {
    alias: { "@": sourceRoot },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: "http://127.0.0.1:7860", changeOrigin: true },
      "/legacy": { target: "http://127.0.0.1:7860", changeOrigin: true },
      "/file=": { target: "http://127.0.0.1:7860", changeOrigin: true },
      "/favicon.ico": { target: "http://127.0.0.1:7860", changeOrigin: true },
    },
  },
  optimizeDeps: {
    // Dev-server dependency pre-bundling still needs esbuild in Vite 5.1+, so a
    // fully esbuild-free `npm run dev` is not possible in this sandbox; the
    // production build below does not use the optimizer.
    noDiscovery: true,
    include: [],
  },
  build: {
    // Relative to `web/`: the FastAPI host prefers this checkout-local build
    // (`web/dist`) and falls back to the copy inside the Python package.
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
    target: "es2020",
    minify: "terser",
    cssMinify: false,
    cssCodeSplit: true,
  },
};
