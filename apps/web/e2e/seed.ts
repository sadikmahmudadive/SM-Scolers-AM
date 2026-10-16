import { Timestamp } from "firebase-admin/firestore";
import { dhakaDate, dhakaInstant, PASSWORD, PEOPLE, PROJECT_ID, punchDocId, USERS } from "./fixtures";
import { emulatorAuth, emulatorDb } from "./emulator";

export type SeedUids = Record<"admin" | "manager" | "staff" | "guardian" | "norole", string>;

async function clearEmulators(): Promise<void> {
  const authHost = process.env.FIREBASE_AUTH_EMULATOR_HOST as string;
  const fsHost = process.env.FIRESTORE_EMULATOR_HOST as string;
  const a = await fetch(`http://${authHost}/emulator/v1/projects/${PROJECT_ID}/accounts`, { method: "DELETE" });
  if (!a.ok) throw new Error(`Could not clear Auth emulator (${a.status})`);
  const f = await fetch(`http://${fsHost}/emulator/v1/projects/${PROJECT_ID}/databases/(default)/documents`, {
    method: "DELETE",
  });
  if (!f.ok) throw new Error(`Could not clear Firestore emulator (${f.status})`);
}

export async function seed(): Promise<SeedUids> {
  emulatorAuth(); // validates the emulator-only guard before anything else
  await clearEmulators();
  const auth = emulatorAuth();
  const db = emulatorDb();

  const uids = {} as SeedUids;
  for (const [who, u] of Object.entries(USERS) as [keyof SeedUids, (typeof USERS)[keyof typeof USERS]][]) {
    const rec = await auth.createUser({ email: u.email, password: PASSWORD, displayName: who, emailVerified: true });
    uids[who] = rec.uid;
    const claims: Record<string, string> = {};
    if (u.role) claims.role = u.role;
    if (who === "staff") claims.personId = PEOPLE.staffSelf.id;
    if (Object.keys(claims).length > 0) await auth.setCustomUserClaims(rec.uid, claims);
    if (u.role) {
      await db
        .collection("users")
        .doc(rec.uid)
        .set({ email: u.email, role: u.role, ...(who === "staff" ? { personId: PEOPLE.staffSelf.id } : {}) });
    }
  }

  const createdAt = Timestamp.now();
  const base = { phone: "", deviceEnrolled: false, active: true, createdAt, guardianUids: [] as string[] };
  await db.collection("people").doc(PEOPLE.rahim.id).set({ ...base, name: PEOPLE.rahim.name, kind: "staff", managerId: uids.manager });
  await db.collection("people").doc(PEOPLE.staffSelf.id).set({ ...base, name: PEOPLE.staffSelf.name, kind: "staff" });
  await db
    .collection("people")
    .doc(PEOPLE.ayesha.id)
    .set({ ...base, name: PEOPLE.ayesha.name, kind: "student", className: "5", guardianUids: [uids.guardian] });
  await db.collection("people").doc(PEOPLE.other.id).set({ ...base, name: PEOPLE.other.name, kind: "student", className: "5" });

  await db
    .collection("schedules")
    .doc("class5")
    .set({ name: "Class 5", start: "08:00", end: "08:15", graceMin: 5, dismissal: "13:00", appliesTo: ["5"] });
  await db.collection("settings").doc("app").set({ timeZone: "Asia/Dhaka", orgName: "E2E School", notificationSound: false });

  const batch = db.batch();
  const punch = (personId: string, date: string, hhmm: string, direction: "in" | "out", late: boolean) => {
    batch.set(db.collection("attendance").doc(punchDocId(personId, date, hhmm)), {
      personId,
      ts: Timestamp.fromDate(dhakaInstant(date, hhmm)),
      date,
      status: direction === "in" ? "check-in" : "check-out",
      direction,
      deviceId: "dev1",
      late,
      earlyLeave: false,
      scheduleId: "class5",
    });
  };
  const today = dhakaDate();
  // A week of history (today and the 6 days before) for 100, 101 and 201; 202 only on older days.
  for (let i = 0; i < 7; i++) {
    const d = dhakaDate(-i);
    punch(PEOPLE.rahim.id, d, "07:50", "in", false);
    punch(PEOPLE.rahim.id, d, "14:00", "out", false);
    if (i > 0) {
      punch(PEOPLE.staffSelf.id, d, "07:55", "in", false);
      punch(PEOPLE.ayesha.id, d, "07:58", "in", false);
      punch(PEOPLE.other.id, d, "07:59", "in", false);
    }
  }
  // Today: Ayesha is late; 101 and 202 have not punched (202 is the live-update target).
  punch(PEOPLE.ayesha.id, today, "08:30", "in", true);
  await batch.commit();
  return uids;
}
