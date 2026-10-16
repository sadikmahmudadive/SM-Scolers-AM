// Runs inside `firebase emulators:exec`: runs Playwright, then prints a marker with its exit code
// so the launcher does not depend on firebase's own wording.
import { spawn } from "node:child_process";

const child = spawn("pnpm", ["--filter", "@hrm/web", "exec", "playwright", "test", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: process.platform === "win32",
});
child.on("exit", (code) => {
  const c = code ?? 1;
  console.log(`[e2e-exit] ${c}`);
  process.exit(c);
});
