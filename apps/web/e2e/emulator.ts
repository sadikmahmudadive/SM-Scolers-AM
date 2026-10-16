import { getApps, initializeApp, type App } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";

/** Admin SDK bound to the emulators ONLY; throws unless both emulator hosts and a demo-* project are set. */
export function emulatorApp(): App {
  const authHost = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const fsHost = process.env.FIRESTORE_EMULATOR_HOST;
  const project = process.env.GCLOUD_PROJECT ?? process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  if (!authHost || !fsHost) {
    throw new Error("E2E refuses to run without FIREBASE_AUTH_EMULATOR_HOST and FIRESTORE_EMULATOR_HOST (use pnpm e2e)");
  }
  if (!project || !project.startsWith("demo-")) {
    throw new Error("E2E refuses to run unless the project id is a demo-* id");
  }
  const existing = getApps().find((a) => a.name === "e2e");
  if (existing) return existing;
  return initializeApp({ projectId: project }, "e2e");
}

export function emulatorAuth() {
  return getAuth(emulatorApp());
}

export function emulatorDb() {
  return getFirestore(emulatorApp());
}
