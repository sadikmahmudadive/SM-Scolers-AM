import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { assertNoEmulatorInProduction } from "./emulator-guard";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";

let emulatorConnected = false;

export function firebaseOptions() {
  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    databaseURL: process.env.NEXT_PUBLIC_FIREBASE_DATABASE_URL,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
  };
}

function app(): FirebaseApp {
  // A named "live" app may exist (firebase-live.ts), so check for the default app specifically.
  if (getApps().some((a) => a.name === "[DEFAULT]")) return getApp();
  return initializeApp(firebaseOptions());
}

export function getClientAuth(): Auth {
  const auth = getAuth(app());
  const host = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;
  if (host && !emulatorConnected) {
    assertNoEmulatorInProduction({ NODE_ENV: process.env.NODE_ENV, NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST: host }, [
      "NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST",
    ]);
    connectAuthEmulator(auth, `http://${host}`, { disableWarnings: true });
    emulatorConnected = true;
  }
  return auth;
}
