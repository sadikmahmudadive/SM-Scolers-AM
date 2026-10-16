"use server";

import type { Role } from "@hrm/shared";
import { getAdminAuth, getAdminDb } from "@/lib/firebase-admin";
import { getSession } from "@/lib/session";
import { applyUserRole } from "@/lib/user-role";

export async function setUserRole(uid: string, role: Role, personId?: string): Promise<void> {
  const caller = await getSession();
  await applyUserRole(
    {
      setClaims: (id, claims) => getAdminAuth().setCustomUserClaims(id, claims),
      writeUser: async (id, doc) => {
        await getAdminDb().collection("users").doc(id).set(doc, { merge: true });
      },
    },
    caller,
    uid,
    role,
    personId,
  );
}
