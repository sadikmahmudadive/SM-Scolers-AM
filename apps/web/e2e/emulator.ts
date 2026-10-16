import { getApps, initializeApp, type App } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";

const LOOPBACK = /^(127\.0\.0\.1|localhost|\[::1\]):\d+$/;

/** Validated emulator coordinates; throws unless both hosts are loopback emulators and the project is demo-*. */
export function emulatorEnv(): { authHost: string; firestoreHost: string; projectId: string } {
  const authHost = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const firestoreHost = process.env.FIRESTORE_EMULATOR_HOST;
  const projectId = process.env.GCLOUD_PROJECT ?? process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  if (!authHost || !firestoreHost) {
    throw new Error("E2E refuses to run without FIREBASE_AUTH_EMULATOR_HOST and FIRESTORE_EMULATOR_HOST (use pnpm e2e)");
  }
  if (!LOOPBACK.test(authHost) || !LOOPBACK.test(firestoreHost)) {
    throw new Error("E2E refuses to run: both emulator hosts must be loopback (127.0.0.1, localhost or [::1])");
  }
  if (!projectId || !projectId.startsWith("demo-")) {
    throw new Error("E2E refuses to run unless the project id is a demo-* id");
  }
  return { authHost, firestoreHost, projectId };
}

/** Admin SDK bound to the emulators ONLY. */
export function emulatorApp(): App {
  const { projectId } = emulatorEnv();
  const existing = getApps().find((a) => a.name === "e2e");
  if (existing) return existing;
  return initializeApp({ projectId }, "e2e");
}

export function emulatorAuth() {
  return getAuth(emulatorApp());
}

export function emulatorDb() {
  return getFirestore(emulatorApp());
}
