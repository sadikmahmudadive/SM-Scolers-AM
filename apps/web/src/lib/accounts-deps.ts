import "server-only";
import { COLLECTIONS } from "@hrm/shared";
import { FieldValue } from "firebase-admin/firestore";
import { isRole } from "./access";
import type { AccountsDeps } from "./accounts";
import { getAdminAuth, getAdminDb } from "./firebase-admin";

const MAX_SCAN = 20000;

function code(e: unknown): unknown {
  return typeof e === "object" && e !== null ? (e as { code?: unknown }).code : undefined;
}

export function adminAccountsDeps(): AccountsDeps {
  const people = () => getAdminDb().collection(COLLECTIONS.people);
  return {
    setClaims: (id, claims) => getAdminAuth().setCustomUserClaims(id, claims),
    revokeSessions: (id) => getAdminAuth().revokeRefreshTokens(id),
    writeUser: async (id, doc) => {
      await getAdminDb().collection("users").doc(id).set(doc, { merge: true });
    },
    deleteMarker: FieldValue.delete(),
    createUser: async ({ email, password, displayName }) => {
      const props: { email: string; password: string; emailVerified: boolean; displayName?: string } = {
        email,
        password,
        emailVerified: false,
      };
      if (displayName) props.displayName = displayName;
      const u = await getAdminAuth().createUser(props);
      return { uid: u.uid };
    },
    deleteUser: (uid) => getAdminAuth().deleteUser(uid),
    updateUser: async (uid, props) => {
      await getAdminAuth().updateUser(uid, props);
    },
    personExists: async (id) => (await people().doc(id).get()).exists,
    getAccount: async (uid) => {
      try {
        const u = await getAdminAuth().getUser(uid);
        const role = u.customClaims?.role;
        const pid = u.customClaims?.personId;
        return {
          uid: u.uid,
          role: isRole(role) ? role : undefined,
          personId: typeof pid === "string" && pid ? pid : undefined,
          disabled: u.disabled,
        };
      } catch (e) {
        if (code(e) === "auth/user-not-found") return null;
        throw e;
      }
    },
    countEnabledAdmins: async () => {
      let count = 0;
      let scanned = 0;
      let token: string | undefined;
      do {
        const page = await getAdminAuth().listUsers(1000, token);
        for (const u of page.users) if (!u.disabled && u.customClaims?.role === "admin") count++;
        scanned += page.users.length;
        token = page.pageToken;
      } while (token && scanned < MAX_SCAN);
      return count;
    },
    linkGuardian: async (personId, uid) => {
      await people().doc(personId).update({ guardianUids: FieldValue.arrayUnion(uid) });
    },
    unlinkGuardian: async (personId, uid) => {
      await people().doc(personId).update({ guardianUids: FieldValue.arrayRemove(uid) });
    },
    setManager: async (personId, uid) => {
      await people().doc(personId).update({ managerId: uid === null ? FieldValue.delete() : uid });
    },
  };
}
