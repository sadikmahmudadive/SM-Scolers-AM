import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import { deleteDoc, doc, getDoc, setDoc, updateDoc } from "firebase/firestore";
import { afterAll, beforeAll, beforeEach, describe, it } from "vitest";
import { COLLECTIONS, type Role } from "@hrm/shared";

let env: RulesTestEnvironment;

const rulesPath = fileURLToPath(new URL("../firestore.rules", import.meta.url));
const [emHost, emPort] = (process.env.FIRESTORE_EMULATOR_HOST ?? "127.0.0.1:8089").split(":");

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-hrm",
    firestore: {
      rules: readFileSync(rulesPath, "utf8"),
      host: emHost,
      port: Number(emPort),
    },
  });
});

afterAll(async () => {
  await env.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, "people/p-report"), { name: "Report", managerId: "mgr1", guardianUids: [] });
    await setDoc(doc(db, "people/p-other"), { name: "Other", managerId: "mgr2", guardianUids: [] });
    await setDoc(doc(db, "people/p-student"), { name: "Student", managerId: null, guardianUids: ["guard1"] });
    await setDoc(doc(db, "attendance/a-report"), { personId: "p-report", ts: 1, date: "2026-10-16" });
    await setDoc(doc(db, "attendance/a-other"), { personId: "p-other", ts: 2, date: "2026-10-16" });
    await setDoc(doc(db, "attendance/a-student"), { personId: "p-student", ts: 3, date: "2026-10-16" });
    for (const c of ["schedules", "holidays", "smsLog", "devices", "commands", "settings", "bridgeStatus"]) {
      await setDoc(doc(db, `${c}/x`), { v: 1 });
    }
    await setDoc(doc(db, "users/admin1"), { role: "admin" });
    await setDoc(doc(db, "users/mgr1"), { role: "manager" });
    await setDoc(doc(db, "users/staff1"), { role: "staff", personId: "p-report" });
  });
});

function as(role: Role | null, uid: string, personId?: string) {
  const claims: Record<string, unknown> = {};
  if (role) claims.role = role;
  if (personId) claims.personId = personId;
  return env.authenticatedContext(uid, claims).firestore();
}
const admin = () => as("admin", "admin1");
const manager = () => as("manager", "mgr1");
const staff = () => as("staff", "staff1", "p-report");
const guardian = () => as("guardian", "guard1");
const noRole = () => as(null, "nobody1");

describe("people", () => {
  it("admin reads any person", async () => {
    await assertSucceeds(getDoc(doc(admin(), "people/p-report")));
    await assertSucceeds(getDoc(doc(admin(), "people/p-other")));
  });
  it("admin client writes are denied", async () => {
    await assertFails(setDoc(doc(admin(), "people/new"), { name: "x" }));
    await assertFails(updateDoc(doc(admin(), "people/p-report"), { name: "y" }));
    await assertFails(deleteDoc(doc(admin(), "people/p-report")));
  });
  it("manager reads own report, denied other", async () => {
    await assertSucceeds(getDoc(doc(manager(), "people/p-report")));
    await assertFails(getDoc(doc(manager(), "people/p-other")));
  });
  it("manager cannot write", async () => {
    await assertFails(updateDoc(doc(manager(), "people/p-report"), { name: "y" }));
  });
  it("staff reads own person only", async () => {
    await assertSucceeds(getDoc(doc(staff(), "people/p-report")));
    await assertFails(getDoc(doc(staff(), "people/p-other")));
  });
  it("guardian reads linked child only", async () => {
    await assertSucceeds(getDoc(doc(guardian(), "people/p-student")));
    await assertFails(getDoc(doc(guardian(), "people/p-report")));
  });
  it("user without role claim is denied", async () => {
    await assertFails(getDoc(doc(noRole(), "people/p-report")));
  });
});

describe("attendance", () => {
  it("admin reads any attendance", async () => {
    await assertSucceeds(getDoc(doc(admin(), "attendance/a-report")));
    await assertSucceeds(getDoc(doc(admin(), "attendance/a-other")));
  });
  it("nobody (incl. admin) can write", async () => {
    for (const db of [admin(), manager(), staff(), guardian()]) {
      await assertFails(setDoc(doc(db, "attendance/new"), { personId: "p-report" }));
      await assertFails(updateDoc(doc(db, "attendance/a-report"), { ts: 9 }));
      await assertFails(deleteDoc(doc(db, "attendance/a-report")));
    }
  });
  it("manager reads own report's attendance, denied other's", async () => {
    await assertSucceeds(getDoc(doc(manager(), "attendance/a-report")));
    await assertFails(getDoc(doc(manager(), "attendance/a-other")));
  });
  it("staff reads own attendance only", async () => {
    await assertSucceeds(getDoc(doc(staff(), "attendance/a-report")));
    await assertFails(getDoc(doc(staff(), "attendance/a-other")));
  });
  it("guardian reads linked child's attendance only", async () => {
    await assertSucceeds(getDoc(doc(guardian(), "attendance/a-student")));
    await assertFails(getDoc(doc(guardian(), "attendance/a-report")));
  });
  it("user without role claim is denied", async () => {
    await assertFails(getDoc(doc(noRole(), "attendance/a-report")));
  });
});

describe("settings, commands, devices", () => {
  it("admin reads but cannot write", async () => {
    for (const c of ["settings", "commands", "devices"]) {
      await assertSucceeds(getDoc(doc(admin(), `${c}/x`)));
      await assertFails(setDoc(doc(admin(), `${c}/x`), { v: 2 }));
      await assertFails(deleteDoc(doc(admin(), `${c}/x`)));
    }
  });
  it("non-admin roles cannot read", async () => {
    for (const db of [manager(), staff(), guardian(), noRole()]) {
      for (const c of ["settings", "commands", "devices"]) {
        await assertFails(getDoc(doc(db, `${c}/x`)));
      }
    }
  });
});

describe("smsLog", () => {
  it("admin reads; nobody writes", async () => {
    await assertSucceeds(getDoc(doc(admin(), "smsLog/x")));
    await assertFails(setDoc(doc(admin(), "smsLog/x"), { v: 2 }));
    await assertFails(setDoc(doc(admin(), "smsLog/new"), { v: 2 }));
  });
  it("non-admin roles cannot read", async () => {
    for (const db of [manager(), staff(), guardian(), noRole()]) {
      await assertFails(getDoc(doc(db, "smsLog/x")));
    }
  });
});

describe("bridgeStatus", () => {
  it("admin and manager read; nobody writes", async () => {
    await assertSucceeds(getDoc(doc(admin(), "bridgeStatus/x")));
    await assertSucceeds(getDoc(doc(manager(), "bridgeStatus/x")));
    for (const db of [admin(), manager(), staff(), guardian()]) {
      await assertFails(setDoc(doc(db, "bridgeStatus/x"), { v: 2 }));
    }
  });
  it("staff and guardian cannot read", async () => {
    await assertFails(getDoc(doc(staff(), "bridgeStatus/x")));
    await assertFails(getDoc(doc(guardian(), "bridgeStatus/x")));
  });
});

describe("schedules and holidays", () => {
  it("every role reads; nobody writes", async () => {
    for (const c of ["schedules", "holidays"]) {
      for (const db of [admin(), manager(), staff(), guardian()]) {
        await assertSucceeds(getDoc(doc(db, `${c}/x`)));
        await assertFails(setDoc(doc(db, `${c}/x`), { v: 2 }));
      }
      await assertFails(getDoc(doc(noRole(), `${c}/x`)));
    }
  });
});

describe("users", () => {
  it("a user reads own doc, admin reads all, others denied", async () => {
    await assertSucceeds(getDoc(doc(manager(), "users/mgr1")));
    await assertFails(getDoc(doc(manager(), "users/staff1")));
    await assertSucceeds(getDoc(doc(admin(), "users/staff1")));
    await assertSucceeds(getDoc(doc(noRole(), "users/nobody1")));
  });
  it("nobody writes", async () => {
    await assertFails(setDoc(doc(admin(), "users/admin1"), { role: "admin" }));
    await assertFails(setDoc(doc(manager(), "users/mgr1"), { role: "admin" }));
  });
});

describe("unmatched collections", () => {
  it("are denied", async () => {
    await assertFails(getDoc(doc(admin(), "mystery/x")));
    await assertFails(setDoc(doc(admin(), "mystery/x"), { v: 1 }));
  });
});

describe("unauthenticated", () => {
  it.each(Object.values(COLLECTIONS))("denied on %s", async (c) => {
    const db = env.unauthenticatedContext().firestore();
    await assertFails(getDoc(doc(db, `${c}/x`)));
    await assertFails(setDoc(doc(db, `${c}/x`), { v: 1 }));
  });
});
