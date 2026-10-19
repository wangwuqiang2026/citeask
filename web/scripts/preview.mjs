import { installNetUseShim } from "./sandbox-shim.mjs";

installNetUseShim();

const { preview } = await import("vite");
const { viteConfig } = await import("./vite.inline.mjs");

const server = await preview({
  ...viteConfig,
  configFile: false,
  preview: { port: 4173 },
});

server.printUrls();
