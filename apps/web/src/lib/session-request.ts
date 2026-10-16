import { claimsToSession, type Session } from "./access";

export const RECENT_SIGN_IN_SECONDS = 5 * 60;

export type SessionRequestDecision =
  | { kind: "ok"; session: Session }
  | { kind: "reject"; status: 400 | 401 | 403 | 415; error: string };

export function evaluateSessionRequest(input: {
  contentType: string | null;
  origin: string | null;
  requestOrigin: string;
  decoded: { uid: string; role?: unknown; personId?: unknown; auth_time?: number };
  nowSec: number;
}): SessionRequestDecision {
  if (!(input.contentType ?? "").toLowerCase().startsWith("application/json")) {
    return { kind: "reject", status: 415, error: "Content-Type must be application/json" };
  }
  if (input.origin && input.origin !== input.requestOrigin) {
    return { kind: "reject", status: 403, error: "Cross-origin request rejected" };
  }
  const session = claimsToSession(input.decoded);
  if (!session) return { kind: "reject", status: 403, error: "No role assigned" };
  const authTime = input.decoded.auth_time;
  if (typeof authTime !== "number" || input.nowSec - authTime >= RECENT_SIGN_IN_SECONDS) {
    return { kind: "reject", status: 401, error: "Recent sign-in required" };
  }
  return { kind: "ok", session };
}
