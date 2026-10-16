// Runs the Playwright suite inside the Firebase emulators (auth + firestore, demo-hrm project).
// Usage: node apps/web/e2e/run.mjs [playwright args...]  (from anywhere; paths are resolved here)
import { execSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const bin = path.join(repoRoot, "firebase", "node_modules", ".bin", process.platform === "win32" ? "firebase.cmd" : "firebase");
if (!existsSync(bin)) {
  console.error("firebase CLI not found; run pnpm install");
  process.exit(1);
}
const PORTS = [3100, 8089, 9099];
const extra = process.argv.slice(2).map((a) => JSON.stringify(a)).join(" ");
const inner = `pnpm --filter @hrm/web exec playwright test ${extra}`.trim();

/** Windows: the Firestore emulator's java.exe can outlive the run and keep its port busy; free the ports. */
function freePorts() {
  if (process.platform !== "win32") return;
  let out = "";
  try {
    out = execSync("netstat -ano -p tcp", { encoding: "utf8" });
  } catch {
    return;
  }
  const pids = new Set();
  for (const line of out.split(/\r?\n/)) {
    const m = line.match(/^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$/);
    if (m && PORTS.includes(Number(m[1])) && Number(m[2]) > 0) pids.add(m[2]);
  }
  for (const pid of pids) {
    try {
      execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
    } catch {
      // already gone
    }
  }
}

const child = spawn(
  `"${bin}" emulators:exec --config firebase/firebase.json --only auth,firestore --project demo-hrm ${JSON.stringify(inner)}`,
  { cwd: repoRoot, shell: true, stdio: ["inherit", "pipe", "pipe"] },
);
let exitCode = null;
let tail = "";
const onData = (stream) => (chunk) => {
  const text = chunk.toString();
  stream.write(text);
  tail = (tail + text).slice(-2000);
  const m = tail.match(/Script exited successfully|Script "[^\n]*" exited with code (\d+)/);
  if (m && exitCode === null) {
    exitCode = m[0].includes("successfully") ? 0 : Number(m[1]);
    // The CLI is shutting the emulators down; give it a moment, then make sure nothing lingers.
    setTimeout(() => {
      freePorts();
      process.exit(exitCode);
    }, 4000).unref?.();
  }
};
child.stdout.on("data", onData(process.stdout));
child.stderr.on("data", onData(process.stderr));
child.on("exit", (code) => {
  freePorts();
  process.exit(exitCode ?? code ?? 1);
});
