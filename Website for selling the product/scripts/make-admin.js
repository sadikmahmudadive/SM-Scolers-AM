/**
 * Promote a user to admin role in Firestore.
 *
 * Usage:
 *   node scripts/make-admin.js <user-email>
 *
 * Requirements:
 *   - A .env file in the project root with NEXT_PUBLIC_FIREBASE_* variables
 *   - The user must have already registered on the site
 *
 * Example:
 *   node scripts/make-admin.js admin@example.com
 */

const { initializeApp } = require("firebase/app");
const {
  getFirestore,
  collection,
  query,
  where,
  getDocs,
  updateDoc,
  doc,
} = require("firebase/firestore");
const { readFileSync } = require("fs");
const { resolve } = require("path");

// Parse .env file
const envPath = resolve(__dirname, "..", ".env");
const envContent = readFileSync(envPath, "utf-8");
const env = {};
for (const line of envContent.split("\n")) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) continue;
  const idx = trimmed.indexOf("=");
  if (idx === -1) continue;
  env[trimmed.slice(0, idx)] = trimmed.slice(idx + 1);
}

const email = process.argv[2];
if (!email) {
  console.error("Usage: node scripts/make-admin.js <user-email>");
  process.exit(1);
}

const firebaseConfig = {
  apiKey: env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

async function makeAdmin() {
  console.log(`Searching for user: ${email} ...`);

  const q = query(collection(db, "users"), where("email", "==", email));
  const snap = await getDocs(q);

  if (snap.empty) {
    console.error(`No user found with email: ${email}`);
    console.error("Make sure the user has registered on the site first.");
    process.exit(1);
  }

  const userDoc = snap.docs[0];
  const userData = userDoc.data();

  if (userData.role === "admin") {
    console.log(`User ${email} is already an admin.`);
    process.exit(0);
  }

  await updateDoc(doc(db, "users", userDoc.id), { role: "admin" });
  console.log(`✓ ${email} has been promoted to admin!`);
  console.log(`  Name: ${userData.name || "(not set)"}`);
  console.log(`  UID:  ${userDoc.id}`);
  console.log(`\nThey can now access /admin after signing in.`);
  process.exit(0);
}

makeAdmin().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
