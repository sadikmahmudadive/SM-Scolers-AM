// Runs inside `firebase emulators:exec`: runs the Playwright CLI directly (no shell, so arguments with
// spaces survive intact), then prints a marker with its exit code for the launcher.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.resolve(here, "..");
const cli = createRequire(path.join(webDir, "package.json")).resolve("@playwright/test/cli");

const child = spawn(process.execPath, [cli, "test", ...process.argv.slice(2)], { cwd: webDir, stdio: "inherit" });
child.on("error", (e) => {
  console.error(`failed to start Playwright: ${e.message}`);
  console.log("[e2e-exit] 1");
  process.exit(1);
});
child.on("exit", (code, signal) => {
  const c = code ?? (signal ? 1 : 1); // a signal/crash is always non-zero
  console.log(`[e2e-exit] ${c}`);
  process.exit(c);
});
