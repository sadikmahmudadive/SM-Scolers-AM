import "server-only";
import { COLLECTIONS } from "@hrm/shared";
import { FieldValue } from "firebase-admin/firestore";
import { getAdminDb } from "./firebase-admin";
import type { PeopleDeps } from "./people";

const GET_ALL_CHUNK = 300;

export function adminPeopleDeps(): PeopleDeps {
  const col = () => getAdminDb().collection(COLLECTIONS.people);
  return {
    now: () => new Date(),
    deleteMarker: FieldValue.delete(),
    create: async (id, data) => {
      await col().doc(id).create(data);
    },
    update: async (id, patch) => {
      await col().doc(id).update(patch);
    },
    // Deletes the people doc only; attendance history is kept on purpose.
    remove: async (id) => {
      await col().doc(id).delete();
    },
    existingIds: async (ids) => {
      const found = new Set<string>();
      for (let i = 0; i < ids.length; i += GET_ALL_CHUNK) {
        const refs = ids.slice(i, i + GET_ALL_CHUNK).map((id) => col().doc(id));
        const snaps = await getAdminDb().getAll(...refs);
        for (const s of snaps) if (s.exists) found.add(s.id);
      }
      return found;
    },
    createMany: async (items) => {
      const batch = getAdminDb().batch();
      for (const it of items) batch.create(col().doc(it.id), it.data);
      await batch.commit();
    },
  };
}
