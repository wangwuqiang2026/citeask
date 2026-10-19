import { installNetUseShim } from "./sandbox-shim.mjs";

installNetUseShim();

const { createServer } = await import("vite");
const { viteConfig } = await import("./vite.inline.mjs");

const server = await createServer({
  ...viteConfig,
  configFile: false,
  mode: "development",
});

await server.listen();
server.printUrls();
