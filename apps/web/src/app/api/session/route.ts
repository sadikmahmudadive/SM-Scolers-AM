import { NextResponse } from "next/server";
import { z } from "zod";
import { claimsToSession } from "@/lib/access";
import { getAdminAuth } from "@/lib/firebase-admin";
import { SESSION_COOKIE, SESSION_MAX_AGE_MS } from "@/lib/session";

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

export async function POST(request: Request) {
  const body = bodySchema.safeParse(await request.json().catch(() => null));
  if (!body.success) return NextResponse.json({ error: "idToken required" }, { status: 400 });

  const auth = getAdminAuth();
  let session;
  try {
    const decoded = await auth.verifyIdToken(body.data.idToken);
    session = claimsToSession(decoded);
  } catch {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }
  if (!session) return NextResponse.json({ error: "No role assigned" }, { status: 403 });

  const cookie = await auth.createSessionCookie(body.data.idToken, { expiresIn: SESSION_MAX_AGE_MS });
  const res = NextResponse.json({ role: session.role });
  res.cookies.set(SESSION_COOKIE, cookie, cookieOptions(SESSION_MAX_AGE_MS / 1000));
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  return res;
}
