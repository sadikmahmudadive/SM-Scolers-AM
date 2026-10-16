import { ROLES, type Role } from "@hrm/shared";

export type Session = { uid: string; role: Role; personId?: string };

export type AccessDecision = { kind: "ok" } | { kind: "redirect"; to: string };

const HOMES: Record<Role, string> = {
  admin: "/dashboard",
  manager: "/team",
  staff: "/me",
  guardian: "/children",
};

export function homeFor(role: Role): string {
  return HOMES[role];
}

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

export function decideAccess(session: Session | null, allowed: readonly Role[]): AccessDecision {
  if (!session) return { kind: "redirect", to: "/login" };
  if (!allowed.includes(session.role)) return { kind: "redirect", to: homeFor(session.role) };
  return { kind: "ok" };
}

/** Maps decoded token / session-cookie claims to a Session, or null when the role claim is invalid. */
export function claimsToSession(decoded: { uid: string; role?: unknown; personId?: unknown }): Session | null {
  if (!isRole(decoded.role)) return null;
  const session: Session = { uid: decoded.uid, role: decoded.role };
  if (typeof decoded.personId === "string" && decoded.personId.length > 0) {
    session.personId = decoded.personId;
  }
  return session;
}
