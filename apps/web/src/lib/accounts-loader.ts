import "server-only";
import { COLLECTIONS } from "@hrm/shared";
import { isRole } from "./access";
import { collectPaged, mergeAccounts, type AccountRow, type AuthUserLike } from "./accounts";
import { getAdminAuth, getAdminDb } from "./firebase-admin";

export const MAX_ACCOUNTS = 2000;
export const MAX_PERSON_OPTIONS = 500;

export type PersonOption = { id: string; name: string; kind: string };
export type SlimAccount = { uid: string; email: string; displayName: string };

/** Lists up to MAX_ACCOUNTS auth users; truncated is true when more exist. */
export async function listAuthUsers(): Promise<{ users: AuthUserLike[]; truncated: boolean }> {
  const { items, truncated } = await collectPaged<AuthUserLike>(async (token) => {
    const page = await getAdminAuth().listUsers(1000, token);
    return { items: page.users, nextToken: page.pageToken };
  }, MAX_ACCOUNTS);
  return { users: items, truncated };
}

export async function loadPeopleOptions(): Promise<{ options: PersonOption[]; truncated: boolean }> {
  const snap = await getAdminDb()
    .collection(COLLECTIONS.people)
    .orderBy("name")
    .limit(MAX_PERSON_OPTIONS + 1)
    .get();
  const options = snap.docs.slice(0, MAX_PERSON_OPTIONS).map((d) => ({
    id: d.id,
    name: String(d.get("name") ?? ""),
    kind: String(d.get("kind") ?? ""),
  }));
  return { options, truncated: snap.docs.length > MAX_PERSON_OPTIONS };
}

async function personNames(ids: string[]): Promise<Map<string, { name: string }>> {
  const out = new Map<string, { name: string }>();
  for (let i = 0; i < ids.length; i += 300) {
    const refs = ids.slice(i, i + 300).map((id) => getAdminDb().collection(COLLECTIONS.people).doc(id));
    for (const s of await getAdminDb().getAll(...refs)) {
      if (s.exists) out.set(s.id, { name: String(s.get("name") ?? "") });
    }
  }
  return out;
}

export async function loadAccountRows(): Promise<{ rows: AccountRow[]; truncated: boolean }> {
  const { users, truncated } = await listAuthUsers();
  const ids = [
    ...new Set(
      users
        .map((u) => u.customClaims?.personId)
        .filter((p): p is string => typeof p === "string" && p.length > 0 && !p.includes("/")),
    ),
  ];
  const rows = mergeAccounts(users, await personNames(ids));
  rows.sort((a, b) => a.email.localeCompare(b.email));
  return { rows, truncated };
}

/** Enabled accounts holding one of the given roles, for select lists (pure filter over an already loaded list). */
export function filterAccountsByRole(users: AuthUserLike[], ...roles: string[]): SlimAccount[] {
  return users
    .filter((u) => isRole(u.customClaims?.role) && roles.includes(String(u.customClaims?.role)) && !u.disabled)
    .map((u) => ({ uid: u.uid, email: u.email ?? "", displayName: u.displayName ?? "" }))
    .sort((a, b) => a.email.localeCompare(b.email));
}

/** Resolves uids to display info; unknown uids come back with known=false. */
export async function resolveAccounts(uids: string[]): Promise<(SlimAccount & { known: boolean })[]> {
  const out: (SlimAccount & { known: boolean })[] = [];
  for (let i = 0; i < uids.length; i += 100) {
    const chunk = uids.slice(i, i + 100);
    const res = await getAdminAuth().getUsers(chunk.map((uid) => ({ uid })));
    const found = new Map(res.users.map((u) => [u.uid, u]));
    for (const uid of chunk) {
      const u = found.get(uid);
      out.push(
        u
          ? { uid, email: u.email ?? "", displayName: u.displayName ?? "", known: true }
          : { uid, email: "", displayName: "", known: false },
      );
    }
  }
  return out;
}
