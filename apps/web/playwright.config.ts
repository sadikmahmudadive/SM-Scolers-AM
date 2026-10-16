import { defineConfig } from "@playwright/test";

const PORT = 3100;
const authHost = process.env.FIREBASE_AUTH_EMULATOR_HOST ?? "127.0.0.1:9099";
const firestoreHost = process.env.FIRESTORE_EMULATOR_HOST ?? "127.0.0.1:8089";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
    // Locally use the installed Chrome; CI downloads Playwright's chromium instead.
    ...(process.env.CI ? {} : { channel: "chrome" }),
  },
  webServer: {
    // `next dev`, not `next start`: production deliberately refuses emulator env vars.
    command: `pnpm exec next dev -p ${PORT}`,
    url: `http://localhost:${PORT}/login`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_FIREBASE_API_KEY: "fake-api-key",
      NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: "localhost",
      NEXT_PUBLIC_FIREBASE_PROJECT_ID: "demo-hrm",
      NEXT_PUBLIC_FIREBASE_APP_ID: "1:1:web:1",
      NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST: authHost,
      NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST: firestoreHost,
      FIREBASE_AUTH_EMULATOR_HOST: authHost,
      FIRESTORE_EMULATOR_HOST: firestoreHost,
      GCLOUD_PROJECT: "demo-hrm",
    },
  },
});
