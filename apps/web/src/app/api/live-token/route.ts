import { NextResponse, type NextRequest } from "next/server";
import { getAdminAuth } from "@/lib/firebase-admin";
import { decideLiveTokenRequest } from "@/lib/live-token";
import { getSession } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const NO_STORE = { "Cache-Control": "no-store" };

/** Mints a Firebase custom token so client Firestore listeners can authenticate (the session cookie is httpOnly). */
export async function GET(request: NextRequest) {
  const decision = decideLiveTokenRequest({
    session: await getSession(),
    origin: request.headers.get("origin"),
    requestOrigin: new URL(request.url).origin,
  });
  if (decision.kind === "reject") {
    return NextResponse.json({ error: decision.error }, { status: decision.status, headers: NO_STORE });
  }
  try {
    const token = await getAdminAuth().createCustomToken(decision.uid, decision.claims);
    return NextResponse.json({ token }, { headers: NO_STORE });
  } catch {
    return NextResponse.json({ error: "Could not create token" }, { status: 500, headers: NO_STORE });
  }
}
