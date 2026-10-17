// Creates (or promotes) an admin account with the Firebase Admin SDK.
//
//   pnpm --filter @hrm/web create-admin -- --email admin@school.example [--name "Head Office"]
//                                          [--reset-password] [--yes] [--project <id>]
//
// Password: env ADMIN_PASSWORD, or an interactive prompt that does not echo.
// Credentials: FIREBASE_SERVICE_ACCOUNT_JSON (inline) or GOOGLE_APPLICATION_CREDENTIALS (file),
// or both emulator hosts (FIREBASE_AUTH_EMULATOR_HOST + FIRESTORE_EMULATOR_HOST).
// The password and the credentials are never printed.
import { readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { parseArgs } from "node:util";
import { Writable } from "node:stream";
import { applicationDefault, cert, initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";

const MIN_PASSWORD_LENGTH = 10;

class UsageError extends Error {}

function fail(message, code = 1) {
  console.error(`create-admin: ${message}`);
  process.exit(code);
}

const USAGE =
  "Usage: create-admin --email <email> [--name <display name>] [--reset-password] [--yes] [--project <id>]\n" +
  `  Password comes from env ADMIN_PASSWORD or a hidden prompt (min ${MIN_PASSWORD_LENGTH} characters).\n` +
  "  Credentials: FIREBASE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS, or both emulator hosts.";

/** Reads one line. With muted=true the typed characters are not echoed. */
function ask(question, { muted = false } = {}) {
  return new Promise((resolve, reject) => {
    let hidden = false;
    const out = new Writable({
      write(chunk, _enc, cb) {
        if (!hidden) process.stdout.write(chunk);
        cb();
      },
    });
    const rl = createInterface({ input: process.stdin, output: out, terminal: true });
    process.stdout.write(question);
    hidden = muted;
    rl.once("close", () => reject(new UsageError("input closed before an answer was given")));
    rl.question("", (answer) => {
      hidden = false;
      if (muted) process.stdout.write("\n");
      rl.removeAllListeners("close");
      rl.close();
      resolve(answer);
    });
  });
}

function requireTty(what) {
  if (!process.stdin.isTTY) {
    throw new UsageError(`${what}; stdin is not a terminal, so pass it explicitly (ADMIN_PASSWORD env / --yes)`);
  }
}

async function readPassword({ confirmTwice }) {
  const fromEnv = process.env.ADMIN_PASSWORD;
  let password;
  if (fromEnv) {
    password = fromEnv;
  } else {
    requireTty("a password is required (set ADMIN_PASSWORD or run in a terminal)");
    password = await ask("Admin password: ", { muted: true });
    if (confirmTwice) {
      const again = await ask("Repeat password: ", { muted: true });
      if (again !== password) throw new UsageError("passwords do not match");
    }
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    throw new UsageError(`password must be at least ${MIN_PASSWORD_LENGTH} characters`);
  }
  return password;
}

function loadCredentials(requestedProject) {
  const authEmu = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const fsEmu = process.env.FIRESTORE_EMULATOR_HOST;
  if (authEmu || fsEmu) {
    if (!(authEmu && fsEmu)) {
      throw new UsageError("set both FIREBASE_AUTH_EMULATOR_HOST and FIRESTORE_EMULATOR_HOST, or neither");
    }
    const projectId = requestedProject || process.env.GCLOUD_PROJECT || process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
    if (!projectId) throw new UsageError("emulator mode needs --project <id> (or GCLOUD_PROJECT)");
    return { options: { projectId }, projectId, emulator: true };
  }

  const inline = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  const file = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  let json;
  if (inline) {
    try {
      json = JSON.parse(inline);
    } catch {
      throw new UsageError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON");
    }
  } else if (file) {
    try {
      json = JSON.parse(readFileSync(file, "utf8"));
    } catch {
      throw new UsageError("could not read GOOGLE_APPLICATION_CREDENTIALS as a service account JSON file");
    }
  } else {
    throw new UsageError(
      "no credentials: set FIREBASE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS (or both emulator hosts)",
    );
  }
  const keyProject = json.project_id;
  if (typeof keyProject !== "string" || !keyProject) throw new UsageError("the service account has no project_id");
  if (!requestedProject) {
    throw new UsageError(
      `refusing to touch project "${keyProject}" without an explicit --project ${keyProject} (production safety check)`,
    );
  }
  if (requestedProject !== keyProject) {
    throw new UsageError(`--project "${requestedProject}" does not match the credentials' project "${keyProject}"`);
  }
  return {
    options: { credential: inline ? cert(json) : applicationDefault(), projectId: keyProject },
    projectId: keyProject,
    emulator: false,
  };
}

async function main() {
  let values;
  try {
    ({ values } = parseArgs({
      options: {
        email: { type: "string" },
        name: { type: "string" },
        project: { type: "string" },
        "reset-password": { type: "boolean", default: false },
        yes: { type: "boolean", default: false },
        help: { type: "boolean", default: false },
      },
      strict: true,
    }));
  } catch (e) {
    throw new UsageError(`${e.message}\n${USAGE}`);
  }
  if (values.help) {
    console.log(USAGE);
    return;
  }
  const email = (values.email ?? "").trim().toLowerCase();
  if (!email) throw new UsageError(`--email is required\n${USAGE}`);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new UsageError("--email is not a valid email address");
  const name = values.name?.trim();
  if (values.name !== undefined && !name) throw new UsageError("--name must not be empty");

  const creds = loadCredentials(values.project?.trim());
  const app = initializeApp(creds.options);
  const auth = getAuth(app);
  const db = getFirestore(app);
  console.log(`Project: ${creds.projectId}${creds.emulator ? " (emulator)" : ""}`);

  let existing = null;
  try {
    existing = await auth.getUserByEmail(email);
  } catch (e) {
    if (e?.code !== "auth/user-not-found") throw e;
  }

  let uid;
  let displayName;
  if (existing) {
    if (!values.yes) {
      requireTty(`${email} already exists; confirmation is required`);
      const what = values["reset-password"] ? " and reset its password" : "";
      const answer = (await ask(`Account ${email} already exists. Make it an admin${what}? [y/N] `)).trim().toLowerCase();
      if (answer !== "y" && answer !== "yes") throw new UsageError("aborted, nothing was changed");
    }
    const update = {};
    if (values["reset-password"]) update.password = await readPassword({ confirmTwice: true });
    if (name) update.displayName = name;
    if (Object.keys(update).length > 0) await auth.updateUser(existing.uid, update);
    uid = existing.uid;
    displayName = name || existing.displayName || email.split("@")[0];
  } else {
    if (values["reset-password"]) console.log("Note: --reset-password has no effect, the account is new.");
    const password = await readPassword({ confirmTwice: true });
    displayName = name || email.split("@")[0];
    ({ uid } = await auth.createUser({ email, password, displayName }));
  }

  await auth.setCustomUserClaims(uid, { role: "admin" });
  await db.collection("users").doc(uid).set({ role: "admin", displayName, email }, { merge: true });
  await auth.revokeRefreshTokens(uid);
  console.log(`${existing ? "Promoted" : "Created"} admin ${email} (uid ${uid}). Existing sessions were revoked; sign in again.`);
}

main().then(
  () => process.exit(0),
  (e) => {
    if (e instanceof UsageError) fail(e.message, 2);
    // Never echo a raw error object: keep to the code and message only.
    fail(`failed (${e?.code ?? "error"}): ${e?.message ?? "unknown error"}`);
  },
);
