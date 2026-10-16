import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { getAdminAuth } from "@/lib/firebase-admin";
import { SESSION_COOKIE, SESSION_MAX_AGE_MS } from "@/lib/session";
import { evaluateSessionRequest } from "@/lib/session-request";

export const runtime = "nodejs";

const bodySchema = z.object({ idToken: z.string().min(1) });

function cookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type");
  const origin = request.headers.get("origin");
  const requestOrigin = new URL(request.url).origin;
  if (!(contentType ?? "").toLowerCase().startsWith("application/json")) {
    return NextResponse.json({ error: "Content-Type must be application/json" }, { status: 415 });
  }
  if (origin && origin !== requestOrigin) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }
  const body = bodySchema.safeParse(await request.json().catch(() => null));
  if (!body.success) return NextResponse.json({ error: "idToken required" }, { status: 400 });

  const auth = getAdminAuth();
  try {
    const decoded = await auth.verifyIdToken(body.data.idToken);
    const decision = evaluateSessionRequest({
      contentType,
      origin,
      requestOrigin,
      decoded,
      nowSec: Date.now() / 1000,
    });
    if (decision.kind === "reject") {
      return NextResponse.json({ error: decision.error }, { status: decision.status });
    }
    const cookie = await auth.createSessionCookie(body.data.idToken, { expiresIn: SESSION_MAX_AGE_MS });
    const res = NextResponse.json({ role: decision.session.role });
    res.cookies.set(SESSION_COOKIE, cookie, cookieOptions(SESSION_MAX_AGE_MS / 1000));
    return res;
  } catch {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }
}

export async function DELETE(request: NextRequest) {
  const cookie = request.cookies.get(SESSION_COOKIE)?.value;
  if (cookie) {
    try {
      const auth = getAdminAuth();
      const decoded = await auth.verifySessionCookie(cookie);
      await auth.revokeRefreshTokens(decoded.sub);
    } catch {
      // best-effort
    }
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  return res;
}
