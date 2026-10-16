import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Role } from "@hrm/shared";
import { claimsToSession, decideAccess, type Session } from "./access";
import { getAdminAuth } from "./firebase-admin";

export { homeFor } from "./access";
export type { Session } from "./access";

export const SESSION_COOKIE = "__session";
export const SESSION_MAX_AGE_MS = 5 * 24 * 60 * 60 * 1000;

export async function getSession(): Promise<Session | null> {
  const cookie = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!cookie) return null;
  try {
    const decoded = await getAdminAuth().verifySessionCookie(cookie, true);
    return claimsToSession(decoded);
  } catch {
    return null;
  }
}

export async function requireRole(...roles: Role[]): Promise<Session> {
  const session = await getSession();
  const decision = decideAccess(session, roles);
  if (decision.kind === "redirect") redirect(decision.to);
  return session as Session;
}
