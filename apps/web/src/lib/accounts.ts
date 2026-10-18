import { ROLES, type Role } from "@hrm/shared";
import { z } from "zod";
import { isRole, type Session } from "./access";
import { PERSON_ID_PATTERN } from "./csv";
import { applyUserRole, type UserRoleDeps } from "./user-role";

export const MIN_PASSWORD_LENGTH = 8;

export type AccountInfo = { uid: string; role?: Role; personId?: string; disabled: boolean };

export type AccountsDeps = UserRoleDeps & {
  /** Admin SDK createUser. Returns the new uid. */
  createUser: (args: { email: string; password: string; displayName?: string }) => Promise<{ uid: string }>;
  deleteUser: (uid: string) => Promise<void>;
  updateUser: (uid: string, props: { disabled?: boolean; password?: string }) => Promise<void>;
  personExists: (personId: string) => Promise<boolean>;
  /** Returns null when the account does not exist. */
  getAccount: (uid: string) => Promise<AccountInfo | null>;
  /** Number of enabled accounts whose role claim is admin. */
  countEnabledAdmins: () => Promise<number>;
  /** people/{id}.guardianUids arrayUnion (idempotent). */
  linkGuardian: (personId: string, uid: string) => Promise<void>;
  /** people/{id}.guardianUids arrayRemove (no-op when absent). */
  unlinkGuardian: (personId: string, uid: string) => Promise<void>;
  /** Sets people/{id}.managerId, or clears it with null. */
  setManager: (personId: string, uid: string | null) => Promise<void>;
};

export type AccountResult = { ok: true } | { ok: false; error: string };
export type CreateAccountResult = { ok: true; uid: string } | { ok: false; error: string };

function assertAdmin(caller: Session | null): asserts caller is Session {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
}

function firstIssue(e: z.ZodError): string {
  const i = e.issues[0];
  if (!i) return "Invalid input";
  const path = i.path.join(".");
  return path ? `${path}: ${i.message}` : i.message;
}

/** Maps a thrown error to a message that can never contain request data such as a password. */
function safeError(e: unknown): string {
  const code = typeof e === "object" && e !== null ? (e as { code?: unknown }).code : undefined;
  switch (code) {
    case "auth/email-already-exists":
      return "An account with this email already exists";
    case "auth/user-not-found":
      return "Account not found";
    case "auth/invalid-email":
      return "Invalid email address";
    case "auth/invalid-password":
    case "auth/weak-password":
      return "The password was rejected";
    default:
      return typeof code === "string" ? `Request failed (${code})` : "Request failed";
  }
}

const passwordSchema = z.string().min(MIN_PASSWORD_LENGTH, `Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
const uidSchema = z.string().min(1, "Account is required");
const personIdSchema = z.string().regex(PERSON_ID_PATTERN, "Invalid person ID");

const createSchema = z.object({
  email: z.string().trim().toLowerCase().pipe(z.email("Enter a valid email")),
  password: passwordSchema,
  displayName: z.string().trim().min(1).max(200).optional(),
  role: z.enum(ROLES),
  personId: personIdSchema.optional(),
});
export type CreateAccountInput = {
  email: string;
  password: string;
  displayName?: string;
  role: Role;
  personId?: string;
};

/** Shared role/personId rules; returns an error message or null. Touches deps only to check the person exists. */
async function checkRolePerson(deps: AccountsDeps, role: Role, personId: string | undefined): Promise<string | null> {
  if (role === "guardian") {
    return personId ? "Guardian accounts cannot be linked to a person here; link them from the person page" : null;
  }
  if (role === "staff" && !personId) return "A person is required for staff accounts";
  if (personId && !(await deps.personExists(personId))) return "Person not found";
  return null;
}

function claimsFor(role: Role, personId: string | undefined): { role: Role; personId?: string } {
  return personId ? { role, personId } : { role };
}

export async function createAccountWith(
  deps: AccountsDeps,
  caller: Session | null,
  input: CreateAccountInput,
): Promise<CreateAccountResult> {
  assertAdmin(caller);
  const parsed = createSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  const { email, password, displayName, role, personId } = parsed.data;
  try {
    const problem = await checkRolePerson(deps, role, personId);
    if (problem) return { ok: false, error: problem };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
  let uid: string;
  try {
    ({ uid } = await deps.createUser({ email, password, displayName }));
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
  try {
    await deps.setClaims(uid, claimsFor(role, personId));
    const doc: Record<string, unknown> = { role, email };
    if (personId) doc.personId = personId;
    if (displayName) doc.displayName = displayName;
    await deps.writeUser(uid, doc as Parameters<AccountsDeps["writeUser"]>[1]);
  } catch (e) {
    try {
      await deps.deleteUser(uid);
    } catch {
      return {
        ok: false,
        error: `Account setup failed and the partial account could not be removed; delete it manually (uid ${uid}, email ${email})`,
      };
    }
    return { ok: false, error: `Account setup failed and was rolled back (${safeError(e)})` };
  }
  return { ok: true, uid };
}

const changeRoleSchema = z.object({ uid: uidSchema, role: z.enum(ROLES), personId: personIdSchema.optional() });

/** Guards shared by role changes and disabling; returns an error message or null. */
async function checkAdminSafety(deps: AccountsDeps, caller: Session, target: AccountInfo, removesAdmin: boolean, verb: string) {
  if (!removesAdmin) return null;
  if (caller.uid === target.uid) return `You cannot ${verb} yourself`;
  if (target.role === "admin" && !target.disabled && (await deps.countEnabledAdmins()) <= 1) {
    return `You cannot ${verb} the last enabled admin`;
  }
  return null;
}

export async function changeRoleWith(
  deps: AccountsDeps,
  caller: Session | null,
  uid: string,
  role: Role,
  personId?: string,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = changeRoleSchema.safeParse({ uid, role, personId });
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    const target = await deps.getAccount(parsed.data.uid);
    if (!target) return { ok: false, error: "Account not found" };
    const problem =
      (await checkRolePerson(deps, parsed.data.role, parsed.data.personId)) ??
      (await checkAdminSafety(deps, caller, target, parsed.data.role !== "admin", "demote"));
    if (problem) return { ok: false, error: problem };
    // Unchanged role and person: nothing to write, and sessions must not be revoked needlessly.
    if (target.role === parsed.data.role && (target.personId ?? undefined) === parsed.data.personId) {
      return { ok: true };
    }
    await applyUserRole(deps, caller, parsed.data.uid, parsed.data.role, parsed.data.personId);
    if (target.role === "admin" && !target.disabled && parsed.data.role !== "admin" && (await deps.countEnabledAdmins()) === 0) {
      // Concurrent change left no enabled admin: restore the previous admin claims.
      await deps.setClaims(target.uid, claimsFor("admin", target.personId));
      await deps.writeUser(target.uid, { role: "admin", personId: target.personId ?? deps.deleteMarker });
      return { ok: false, error: "That change would leave no enabled admin, so it was reverted" };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

export async function setAccountDisabledWith(
  deps: AccountsDeps,
  caller: Session | null,
  uid: string,
  disabled: boolean,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = uidSchema.safeParse(uid);
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    const target = await deps.getAccount(uid);
    if (!target) return { ok: false, error: "Account not found" };
    const problem = await checkAdminSafety(deps, caller, target, disabled === true, "disable");
    if (problem) return { ok: false, error: problem };
    await deps.updateUser(uid, { disabled });
    if (disabled) {
      await deps.revokeSessions(uid);
      if (target.role === "admin" && !target.disabled && (await deps.countEnabledAdmins()) === 0) {
        await deps.updateUser(uid, { disabled: false });
        return { ok: false, error: "That change would leave no enabled admin, so it was reverted" };
      }
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

export async function resetPasswordWith(
  deps: AccountsDeps,
  caller: Session | null,
  uid: string,
  newPassword: string,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = z.object({ uid: uidSchema, password: passwordSchema }).safeParse({ uid, password: newPassword });
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    await deps.updateUser(parsed.data.uid, { password: parsed.data.password });
    await deps.revokeSessions(parsed.data.uid);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

export async function linkGuardianWith(
  deps: AccountsDeps,
  caller: Session | null,
  personId: string,
  guardianUid: string,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = z.object({ personId: personIdSchema, uid: uidSchema }).safeParse({ personId, uid: guardianUid });
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    if (!(await deps.personExists(parsed.data.personId))) return { ok: false, error: "Person not found" };
    const account = await deps.getAccount(parsed.data.uid);
    if (!account) return { ok: false, error: "Account not found" };
    if (account.role !== "guardian") return { ok: false, error: "Only guardian accounts can be linked as guardians" };
    await deps.linkGuardian(parsed.data.personId, parsed.data.uid);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

export async function unlinkGuardianWith(
  deps: AccountsDeps,
  caller: Session | null,
  personId: string,
  guardianUid: string,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = z.object({ personId: personIdSchema, uid: uidSchema }).safeParse({ personId, uid: guardianUid });
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    if (!(await deps.personExists(parsed.data.personId))) return { ok: false, error: "Person not found" };
    await deps.unlinkGuardian(parsed.data.personId, parsed.data.uid);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

export async function assignManagerWith(
  deps: AccountsDeps,
  caller: Session | null,
  personId: string,
  managerUid: string | null,
): Promise<AccountResult> {
  assertAdmin(caller);
  const parsed = z
    .object({ personId: personIdSchema, uid: uidSchema.nullable() })
    .safeParse({ personId, uid: managerUid });
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  try {
    if (!(await deps.personExists(parsed.data.personId))) return { ok: false, error: "Person not found" };
    if (parsed.data.uid !== null) {
      const account = await deps.getAccount(parsed.data.uid);
      if (!account) return { ok: false, error: "Account not found" };
      if (account.role !== "manager" && account.role !== "admin") {
        return { ok: false, error: "Only manager or admin accounts can be assigned as manager" };
      }
    }
    await deps.setManager(parsed.data.personId, parsed.data.uid);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: safeError(e) };
  }
}

/** Pages through a token-paginated source, keeping at most `cap` items; truncated is true when more exist. */
export async function collectPaged<T>(
  fetchPage: (token?: string) => Promise<{ items: T[]; nextToken?: string }>,
  cap: number,
): Promise<{ items: T[]; truncated: boolean }> {
  const items: T[] = [];
  let token: string | undefined;
  do {
    const page = await fetchPage(token);
    for (const it of page.items) {
      if (items.length >= cap) return { items, truncated: true };
      items.push(it);
    }
    token = page.nextToken;
  } while (token);
  return { items, truncated: false };
}

// ---- view model -------------------------------------------------------------------------------

export type AuthUserLike = {
  uid: string;
  email?: string;
  displayName?: string;
  disabled: boolean;
  customClaims?: Record<string, unknown> | null;
  metadata: { lastSignInTime?: string };
};

export type AccountRow = {
  uid: string;
  email: string;
  displayName: string;
  role: Role | null;
  roleLabel: string;
  personId: string | null;
  personName: string | null;
  disabled: boolean;
  /** ISO string, or null when the account never signed in. */
  lastSignIn: string | null;
};

export const NO_ROLE_LABEL = "no role (cannot sign in)";

export function mergeAccounts(
  users: readonly AuthUserLike[],
  personsById: ReadonlyMap<string, { name: string }>,
): AccountRow[] {
  return users.map((u) => {
    const claims = u.customClaims ?? {};
    const role = isRole(claims.role) ? claims.role : null;
    const personId = typeof claims.personId === "string" && claims.personId ? claims.personId : null;
    const t = u.metadata.lastSignInTime ? new Date(u.metadata.lastSignInTime) : null;
    return {
      uid: u.uid,
      email: u.email ?? "",
      displayName: u.displayName ?? "",
      role,
      roleLabel: role ?? NO_ROLE_LABEL,
      personId,
      personName: personId ? (personsById.get(personId)?.name ?? null) : null,
      disabled: u.disabled,
      lastSignIn: t && !Number.isNaN(t.getTime()) ? t.toISOString() : null,
    };
  });
}
