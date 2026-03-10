/**
 * Promote a user to admin role in Firestore.
 *
 * Usage:
 *   node scripts/make-admin.js <user-email>
 *
 * This temporarily sets permissive Firestore rules aren't needed —
 * it signs you in first, then updates the target user doc.
 *
 * Since only Firebase Console or Admin SDK can bypass rules,
 * this script uses a one-time direct doc update approach:
 * it looks up the user by email, then updates their role.
 *
 * NOTE: Your Firestore rules must temporarily allow this operation.
 * In Firebase Console → Firestore → Rules, temporarily set:
 *   allow read, write: if true;
 * Then run this script, then restore your rules.
 *
 * Alternatively, install firebase-admin and use a service account.
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
  console.log(`Project: ${firebaseConfig.projectId}\n`);

  const q = query(collection(db, "users"), where("email", "==", email));
  let snap;
  try {
    snap = await getDocs(q);
  } catch (err) {
    if (err.code === "permission-denied" || err.message.includes("permissions")) {
      console.error("ERROR: Firestore rules are blocking this operation.\n");
      console.error("To fix, go to Firebase Console → Firestore → Rules and TEMPORARILY set:");
      console.error("  rules_version = '2';");
      console.error("  service cloud.firestore {");
      console.error("    match /databases/{database}/documents {");
      console.error("      match /{document=**} {");
      console.error("        allow read, write: if true;");
      console.error("      }");
      console.error("    }");
      console.error("  }\n");
      console.error("Then run this script again, then restore your secure rules from firestore.rules.");
      process.exit(1);
    }
    throw err;
  }

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
  console.log(`\nIMPORTANT: Restore your secure Firestore rules now!`);
  console.log(`Copy the rules from firestore.rules to Firebase Console → Firestore → Rules.`);
  process.exit(0);
}

makeAdmin().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
