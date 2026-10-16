// Runs the Playwright suite inside the Firebase emulators (auth + firestore, demo-hrm project).
// Usage: node apps/web/e2e/run.mjs [playwright args...]
// Exit codes: suite's own code; 2 = a required port is busy (nothing is started or killed).
import { execSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const win = process.platform === "win32";
const bin = path.join(repoRoot, "firebase", "node_modules", ".bin", win ? "firebase.cmd" : "firebase");
const PORTS = [3100, 8089, 9099];
const SHUTDOWN_GRACE_MS = 30_000;

if (!existsSync(bin)) {
  console.error("firebase CLI not found; run pnpm install");
  process.exit(1);
}

function portBusy(port) {
  const hosts = ["127.0.0.1", "::1"];
  return Promise.all(
    hosts.map(
      (host) =>
        new Promise((resolve) => {
          const s = net.connect({ port, host });
          s.once("connect", () => (s.destroy(), resolve(true)));
          s.once("error", () => resolve(false));
          s.setTimeout(1500, () => (s.destroy(), resolve(false)));
        }),
    ),
  ).then((r) => r.some(Boolean));
}

const busy = [];
for (const p of PORTS) if (await portBusy(p)) busy.push(p);
if (busy.length > 0) {
  console.error(`E2E aborted: port(s) ${busy.join(", ")} already in use. Stop whatever is using them and retry (nothing was killed).`);
  process.exit(2);
}

/** PIDs listening on our ports. Safe to kill: the ports were verified free before this run started. */
function listenerPids() {
  const pids = new Set();
  try {
    if (win) {
      const out = execSync("netstat -ano -p tcp", { encoding: "utf8" });
      for (const line of out.split(/\r?\n/)) {
        const m = line.match(/^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$/);
        if (m && PORTS.includes(Number(m[1])) && Number(m[2]) > 0) pids.add(m[2]);
      }
    } else {
      for (const p of PORTS) {
        try {
          for (const pid of execSync(`lsof -ti tcp:${p} -sTCP:LISTEN`, { encoding: "utf8" }).split(/\s+/)) if (pid) pids.add(pid);
        } catch {
          // none listening
        }
      }
    }
  } catch {
    // best effort
  }
  return pids;
}

function killTree(pid) {
  try {
    if (win) execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
    else process.kill(-Number(pid), "SIGKILL");
  } catch {
    // already gone
  }
}

const inner = `node ${JSON.stringify(path.join(here, "exec-playwright.mjs"))} ${process.argv
  .slice(2)
  .map((a) => JSON.stringify(a))
  .join(" ")}`.trim();
const child = spawn(
  `"${bin}" emulators:exec --config firebase/firebase.json --only auth,firestore --project demo-hrm ${JSON.stringify(inner)}`,
  { cwd: repoRoot, shell: true, stdio: ["inherit", "pipe", "pipe"], detached: !win },
);

let finished = false;
function finish(code, note) {
  if (finished) return;
  finished = true;
  if (note) console.error(note);
  if (child.pid) killTree(child.pid);
  for (const pid of listenerPids()) killTree(pid);
  process.exit(code);
}

let suiteCode = null;
let tail = "";
let graceTimer = null;
let quickKill = false;
const ANSI = /\u001b\[[0-9;]*m/g;
// Captured from real firebase output: "Script exited successfully (code 0)" and
// "Script exited unsuccessfully (code 1)" / 'Error: Script "..." exited with code 1'.
const FIREBASE_EXIT = /Script exited (successfully|unsuccessfully) \(code (\d+)\)|exited with code (\d+)/;

function onData(stream) {
  return (chunk) => {
    const text = chunk.toString();
    stream.write(text);
    tail = (tail + text.replace(ANSI, "")).slice(-4000);
    if (suiteCode === null) {
      const marker = tail.match(/\[e2e-exit\] (\d+)/);
      const fb = tail.match(FIREBASE_EXIT);
      if (marker) suiteCode = Number(marker[1]);
      else if (fb) suiteCode = Number(fb[2] ?? fb[3]);
      if (suiteCode !== null) {
        // The CLI now shuts the emulators down; if it hangs (Windows java), force it after a grace period.
        graceTimer = setTimeout(() => finish(suiteCode, null), SHUTDOWN_GRACE_MS);
      }
    }
    if (suiteCode !== null && !quickKill && /Stopping Logging Emulator/.test(tail)) {
      quickKill = true;
      clearTimeout(graceTimer);
      graceTimer = setTimeout(() => finish(suiteCode, null), 3000);
    }
  };
}
child.stdout.on("data", onData(process.stdout));
child.stderr.on("data", onData(process.stderr));
child.on("exit", (code) => {
  if (graceTimer) clearTimeout(graceTimer);
  if (suiteCode === null) finish(code || 1, "E2E: emulator launcher ended without reporting a test result");
  else finish(suiteCode, null);
});
process.on("SIGINT", () => finish(130, "interrupted"));
