import { NextResponse, type NextRequest } from "next/server";
import { renderToBuffer } from "@react-pdf/renderer";
import { PersonReportDocument } from "@/components/pdf/person-report";
import { loadHolidays, loadOrgName, loadTimeZone, loadWeekendDays, toAttendance, toPerson } from "@/lib/attendance-loader";
import { getAdminDb } from "@/lib/firebase-admin";
import { todayInZone } from "@/lib/org-time";
import {
  PERSON_REPORT_PUNCH_CAP,
  authorizeReportAccess,
  buildPersonReport,
  decideReportResponse,
  reportParamsSchema,
} from "@/lib/person-report";
import { applyScopedSpec, personAttendanceSpec } from "@/lib/scoped-queries";
import { getSession } from "@/lib/session";
import { MAX_RANGE_DAYS, rangeFromPreset } from "@/lib/stats";
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

  // Only this person's punches (personId asc, date desc index); closures come from the
  // holidays and the configured weekend days, so no org-wide data is read.
  const spec = { ...personAttendanceSpec(person.id, range), limit: PERSON_REPORT_PUNCH_CAP + 1 };
  const [punchSnap, holidays, weekendDays, orgName] = await Promise.all([
    applyScopedSpec(getAdminDb(), spec).get(),
    loadHolidays(),
    loadWeekendDays(),
    loadOrgName(),
  ]);
  const outcome = decideReportResponse({ truncated: punchSnap.size > PERSON_REPORT_PUNCH_CAP });
  if (outcome.status === 413) return fail(outcome.error, 413);
  const punches = punchSnap.docs.slice(0, PERSON_REPORT_PUNCH_CAP).map((d) => toAttendance(d.data()));
  const report = buildPersonReport(person, punches, range, holidays, weekendDays, tz, todayInZone(tz, new Date()));
  const buffer = await renderToBuffer(PersonReportDocument({ orgName, person, range, report }));
  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="attendance-${person.id}-${range.from}-${range.to}.pdf"`,
      ...NO_STORE,
    },
  });
}
