import { installNetUseShim } from "./sandbox-shim.mjs";

// Must run before Vite is imported: Vite reads `child_process.exec` on load.
installNetUseShim();

const { build } = await import("vite");
const { viteConfig } = await import("./vite.inline.mjs");

await build({
  ...viteConfig,
  configFile: false,
  mode: "production",
});

console.log("[build] SPA written to web/dist");
