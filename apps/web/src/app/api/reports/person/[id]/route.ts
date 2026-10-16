import { NextResponse, type NextRequest } from "next/server";
import { renderToBuffer } from "@react-pdf/renderer";
import { PersonReportDocument } from "@/components/pdf/person-report";
import { loadOrgName, loadTimeZone, toPerson } from "@/lib/attendance-loader";
import { getAdminDb } from "@/lib/firebase-admin";
import { todayInZone } from "@/lib/org-time";
import { authorizeReportAccess, buildPersonReport, reportParamsSchema } from "@/lib/person-report";
import { getSession } from "@/lib/session";
import { MAX_RANGE_DAYS, rangeFromPreset } from "@/lib/stats";
import { loadStatsData } from "@/lib/stats-loader";
import { COLLECTIONS } from "@hrm/shared";

export const runtime = "nodejs";

const NO_STORE = { "Cache-Control": "no-store" };
const fail = (error: string, status: number) => NextResponse.json({ error }, { status, headers: NO_STORE });

export async function GET(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return fail("Unauthorized", 401);
  if (session.role !== "admin" && session.role !== "manager") return fail("Forbidden", 403);

  const { id } = await ctx.params;
  const tz = await loadTimeZone();
  const defaults = rangeFromPreset("30d", todayInZone(tz, new Date()));
  const sp = request.nextUrl.searchParams;
  const parsed = reportParamsSchema.safeParse({
    id,
    from: sp.get("from") ?? defaults.from,
    to: sp.get("to") ?? defaults.to,
  });
  if (!parsed.success) return fail("Invalid id or date range", 400);
  const range = { from: parsed.data.from, to: parsed.data.to };
  try {
    rangeFromPreset("custom", range.to, range);
  } catch {
    return fail(`Invalid date range (max ${MAX_RANGE_DAYS} days)`, 400);
  }

  const snap = await getAdminDb().collection(COLLECTIONS.people).doc(parsed.data.id).get();
  const person = snap.exists ? toPerson(snap.id, snap.data() ?? {}) : null;
  const decision = authorizeReportAccess(session, person);
  if (decision === "unauthorized") return fail("Unauthorized", 401);
  if (decision === "forbidden") return fail("Forbidden", 403);
  if (decision === "not-found" || !person) return fail("Not found", 404);

  const [data, orgName] = await Promise.all([loadStatsData(range), loadOrgName()]);
  const report = buildPersonReport(person, data.punches, range, data.holidays, tz);
  const buffer = await renderToBuffer(PersonReportDocument({ orgName, person, range, report }));
  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="attendance-${person.id}-${range.from}-${range.to}.pdf"`,
      ...NO_STORE,
    },
  });
}
