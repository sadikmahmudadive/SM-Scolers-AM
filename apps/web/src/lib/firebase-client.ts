import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { assertNoEmulatorInProduction } from "./emulator-guard";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";

let emulatorConnected = false;

function app(): FirebaseApp {
  if (getApps().length > 0) return getApp();
  return initializeApp({
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  });
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
