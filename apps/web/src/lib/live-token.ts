import type { Session } from "./access";

/** Custom tokens last 1h; refresh after ~50 minutes. */
export const REFRESH_AFTER_MS = 50 * 60 * 1000;

export type LiveTokenDecision =
  | { kind: "ok"; uid: string; claims: { role: string; personId?: string } }
  | { kind: "reject"; status: 401 | 403; error: string };

export function decideLiveTokenRequest(input: {
  session: Session | null;
  origin: string | null;
  requestOrigin: string;
}): LiveTokenDecision {
  if (!input.session) return { kind: "reject", status: 401, error: "Not signed in" };
  if (input.origin && input.origin !== input.requestOrigin) {
    return { kind: "reject", status: 403, error: "Cross-origin request rejected" };
  }
  const claims: { role: string; personId?: string } = { role: input.session.role };
  if (input.session.personId) claims.personId = input.session.personId;
  return { kind: "ok", uid: input.session.uid, claims };
}

/** `fetchedAtMs` is when the current token was obtained (null when none). */
export function shouldRefreshToken(fetchedAtMs: number | null, nowMs: number): boolean {
  return fetchedAtMs === null || nowMs - fetchedAtMs > REFRESH_AFTER_MS;
}
