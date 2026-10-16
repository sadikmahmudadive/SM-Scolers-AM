import { NextResponse, type NextRequest } from "next/server";

// /api/live-token and /api/reports are exempt so unauthenticated callers get a JSON 401 instead of a redirect (the route verifies the session itself).
const PUBLIC_PREFIXES = ["/login", "/api/session", "/api/live-token", "/api/reports", "/_next", "/favicon.ico"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  if (!request.cookies.get("__session")?.value) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
