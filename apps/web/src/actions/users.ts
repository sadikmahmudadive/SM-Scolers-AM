"use server";

import type { Role } from "@hrm/shared";
import { FieldValue } from "firebase-admin/firestore";
import { getAdminAuth, getAdminDb } from "@/lib/firebase-admin";
import { getSession } from "@/lib/session";
import { applyUserRole } from "@/lib/user-role";

export async function setUserRole(uid: string, role: Role, personId?: string): Promise<void> {
  const caller = await getSession();
  await applyUserRole(
    {
      setClaims: (id, claims) => getAdminAuth().setCustomUserClaims(id, claims),
      revokeSessions: (id) => getAdminAuth().revokeRefreshTokens(id),
      writeUser: async (id, doc) => {
        await getAdminDb().collection("users").doc(id).set(doc, { merge: true });
      },
      deleteMarker: FieldValue.delete(),
    },
    caller,
    uid,
    role,
    personId,
  );
}
