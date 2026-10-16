import "server-only";
import { getAdminDb } from "./firebase-admin";
import type { SettingsDeps } from "./settings";

function fromFirestore(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    out[k] =
      typeof v === "object" && v !== null && typeof (v as { toDate?: unknown }).toDate === "function"
        ? (v as { toDate: () => Date }).toDate()
        : v;
  }
  return out;
}

export function adminSettingsDeps(): SettingsDeps {
  const db = () => getAdminDb();
  return {
    newId: () => db().collection("schedules").doc().id,
    set: async (collection, id, data, opts) => {
      const ref = db().collection(collection).doc(id);
      if (opts?.merge) await ref.set(data, { merge: true });
      else await ref.set(data);
    },
    remove: async (collection, id) => {
      await db().collection(collection).doc(id).delete();
    },
    get: async (collection, id) => {
      const snap = await db().collection(collection).doc(id).get();
      return snap.exists ? fromFirestore(snap.data() ?? {}) : null;
    },
    list: async (collection) => {
      const snap = await db().collection(collection).get();
      return snap.docs.map((d) => ({ id: d.id, data: fromFirestore(d.data()) }));
    },
    setBatch: async (items) => {
      const batch = db().batch();
      for (const it of items) batch.set(db().collection(it.collection).doc(it.id), it.data);
      await batch.commit();
    },
  };
}
