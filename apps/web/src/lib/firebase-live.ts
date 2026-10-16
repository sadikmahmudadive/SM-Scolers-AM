import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  connectAuthEmulator,
  initializeAuth,
  inMemoryPersistence,
  signInWithCustomToken,
  type Auth,
} from "firebase/auth";
import { connectFirestoreEmulator, getFirestore, type Firestore } from "firebase/firestore";
import { assertNoEmulatorInProduction } from "./emulator-guard";
import { firebaseOptions } from "./firebase-client";
import { REFRESH_AFTER_MS, shouldRefreshToken } from "./live-token";

// A dedicated app so the login flow's default app/auth (which signs out) is untouched.
const LIVE_APP = "live";

let auth: Auth | null = null;
let db: Firestore | null = null;
let fetchedAt: number | null = null;
let inflight: Promise<void> | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;

function liveApp(): FirebaseApp {
  if (getApps().some((a) => a.name === LIVE_APP)) return getApp(LIVE_APP);
  return initializeApp(firebaseOptions(), LIVE_APP);
}

function liveAuth(): Auth {
  if (auth) return auth;
  const a = initializeAuth(liveApp(), { persistence: inMemoryPersistence });
  const host = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;
  if (host) {
    assertNoEmulatorInProduction({ NODE_ENV: process.env.NODE_ENV, NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST: host }, [
      "NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST",
    ]);
    connectAuthEmulator(a, `http://${host}`, { disableWarnings: true });
  }
  auth = a;
  return a;
}

/** Firestore client bound to the live app (authenticated via ensureLiveAuth). */
export function getClientDb(): Firestore {
  if (db) return db;
  const instance = getFirestore(liveApp());
  const host = process.env.NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST;
  if (host) {
    assertNoEmulatorInProduction({ NODE_ENV: process.env.NODE_ENV, NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST: host }, [
      "NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST",
    ]);
    const [h, port] = host.split(":");
    connectFirestoreEmulator(instance, h as string, Number(port));
  }
  db = instance;
  return instance;
}

async function signIn(): Promise<void> {
  const res = await fetch("/api/live-token", { cache: "no-store", credentials: "same-origin" });
  if (!res.ok) throw new Error(`Live token request failed (${res.status})`);
  const body = (await res.json()) as { token?: string };
  if (!body.token) throw new Error("Live token missing");
  await signInWithCustomToken(liveAuth(), body.token);
  fetchedAt = Date.now();
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    void ensureLiveAuth().catch(() => undefined);
  }, REFRESH_AFTER_MS);
}

/** Signs the client SDK in with a server-minted token; concurrent calls share one request; refreshes before expiry. */
export function ensureLiveAuth(): Promise<void> {
  if (!shouldRefreshToken(fetchedAt, Date.now()) && liveAuth().currentUser) return Promise.resolve();
  if (!inflight) {
    inflight = signIn().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}
