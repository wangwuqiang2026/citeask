import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

/**
 * Vite 5 calls `exec("net use")` on Windows to map network drives
 * (`optimizeSafeRealPathSync`). Child processes may not use pipes in this
 * repository's sandbox, so that call throws synchronously with "spawn EPERM".
 *
 * The result of `net use` only affects how UNC paths are rewritten; returning an
 * empty drive list makes Vite fall back to `fs.realpathSync` for local drives,
 * which is exactly what a checkout without mapped network drives needs. The shim
 * is harmless outside the sandbox: with no mapped drives the real command returns
 * the same empty list.
 */
export function installNetUseShim() {
  const childProcess = require("node:child_process");
  const realExec = childProcess.exec;
  if (realExec.__citeaskShim) return;

  const shim = function exec(command, options, callback) {
    const done = typeof options === "function" ? options : callback;
    if (typeof command === "string" && command.trim() === "net use") {
      if (typeof done === "function") queueMicrotask(() => done(null, "", ""));
      return {
        on() {},
        once() {},
        kill() {},
        stdin: null,
        stdout: null,
        stderr: null,
      };
    }
    return realExec.call(childProcess, command, options, callback);
  };
  shim.__citeaskShim = true;
  childProcess.exec = shim;
}
