import { ROLES, type Role } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";

export type UserDoc = { role: Role; personId?: unknown; displayName?: string };

export type UserRoleDeps = {
  setClaims: (uid: string, claims: { role: Role; personId?: string }) => Promise<void>;
  revokeSessions: (uid: string) => Promise<void>;
  writeUser: (uid: string, doc: UserDoc) => Promise<void>;
  /** Firestore FieldValue.delete() sentinel, injected so this module stays pure. */
  deleteMarker: unknown;
};

const inputSchema = z.object({
  uid: z.string().min(1),
  role: z.enum(ROLES),
  personId: z.string().min(1).optional(),
});

export async function applyUserRole(
  deps: UserRoleDeps,
  caller: Session | null,
  uid: string,
  role: Role,
  personId?: string,
): Promise<void> {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
  const input = inputSchema.parse({ uid, role, personId });
  const claims = input.personId ? { role: input.role, personId: input.personId } : { role: input.role };
  await deps.setClaims(input.uid, claims);
  await deps.revokeSessions(input.uid);
  await deps.writeUser(input.uid, {
    role: input.role,
    personId: input.personId ?? deps.deleteMarker,
  });
}
