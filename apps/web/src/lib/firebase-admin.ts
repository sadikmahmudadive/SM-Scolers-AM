import "server-only";
import { applicationDefault, cert, getApp, getApps, initializeApp, type App } from "firebase-admin/app";
import { getAuth, type Auth } from "firebase-admin/auth";
import { getFirestore, type Firestore } from "firebase-admin/firestore";
import { assertNoEmulatorInProduction } from "./emulator-guard";

function adminApp(): App {
  if (getApps().length > 0) return getApp();
  assertNoEmulatorInProduction(process.env, ["FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"]);
  const projectId = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  const inline = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (inline) {
    let parsed: object;
    try {
      parsed = JSON.parse(inline);
    } catch {
      throw new Error("invalid FIREBASE_SERVICE_ACCOUNT_JSON");
    }
    return initializeApp({ credential: cert(parsed), projectId });
  }
  if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    return initializeApp({ credential: applicationDefault(), projectId });
  }
  if (process.env.FIREBASE_AUTH_EMULATOR_HOST || process.env.FIRESTORE_EMULATOR_HOST) {
    return initializeApp({ projectId });
  }
  throw new Error(
    "Firebase Admin is not configured: set FIREBASE_SERVICE_ACCOUNT_JSON, GOOGLE_APPLICATION_CREDENTIALS or an emulator host.",
  );
}

export function getAdminAuth(): Auth {
  return getAuth(adminApp());
}

export function getAdminDb(): Firestore {
  return getFirestore(adminApp());
}
