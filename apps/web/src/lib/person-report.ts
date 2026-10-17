import type { Attendance, Person } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";
import { PERSON_ID_PATTERN } from "./csv";
import { formatTimeInZone } from "./org-time";
import { eachDate } from "./stats";

export type ReportAccess = "ok" | "unauthorized" | "forbidden" | "not-found";

export function authorizeReportAccess(
  session: Session | null,
  person: { managerId?: string } | null,
): ReportAccess {
  if (!session) return "unauthorized";
  if (!person) return "not-found";
  if (session.role === "admin") return "ok";
  if (session.role === "manager" && person.managerId && person.managerId === session.uid) return "ok";
  return "forbidden";
}

const dateStr = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const reportParamsSchema = z
  .object({ id: z.string().regex(PERSON_ID_PATTERN).max(64), from: dateStr, to: dateStr })
  .refine((v) => v.from <= v.to, { message: "from must not be after to" });

export type ReportDay = {
  date: string;
  first: string | null;
  last: string | null;
  directions: string;
  late: boolean;
  earlyLeave: boolean;
  punches: number;
  absent: boolean;
};
export type ReportSummary = { present: number; late: number; earlyLeave: number; punches: number; absent: number };
export type PersonReport = { days: ReportDay[]; summary: ReportSummary };

/** Upper bound on one person's punches loaded for a report (366 days of ~13 punches a day). */
export const PERSON_REPORT_PUNCH_CAP = 5000;

/** A school day is any date that is not a holiday and whose weekday is not a weekend day. */
export function isSchoolDay(date: string, holidays: ReadonlySet<string>, weekendDays: readonly number[]): boolean {
  if (holidays.has(date)) return false;
  return !weekendDays.includes(new Date(`${date}T00:00:00Z`).getUTCDay());
}

/**
 * `punches` are this person's punches in the range (others are ignored). Every school day up to
 * `today` (org-local yyyy-MM-dd) without a punch is an absence; a holiday or weekend day is
 * listed only when the person punched on it (never as absent).
 */
export function buildPersonReport(
  person: Pick<Person, "kind"> & { id: string },
  punches: readonly Attendance[],
  range: { from: string; to: string },
  holidays: readonly string[],
  weekendDays: readonly number[],
  timeZone: string,
  today: string,
): PersonReport {
  const holiday = new Set(holidays);
  const mine = new Map<string, Attendance[]>();
  for (const p of punches) {
    if (p.personId !== person.id) continue;
    const list = mine.get(p.date) ?? [];
    list.push(p);
    mine.set(p.date, list);
  }
  const days: ReportDay[] = [];
  for (const date of eachDate(range)) {
    if (date > today) break;
    const list = (mine.get(date) ?? []).sort((a, b) => a.ts.getTime() - b.ts.getTime());
    if (list.length === 0 && !isSchoolDay(date, holiday, weekendDays)) continue;
    if (list.length === 0) {
      days.push({ date, first: null, last: null, directions: "", late: false, earlyLeave: false, punches: 0, absent: true });
      continue;
    }
    days.push({
      date,
      first: formatTimeInZone(timeZone, list[0]!.ts),
      last: formatTimeInZone(timeZone, list[list.length - 1]!.ts),
      directions: list.map((p) => p.direction).join(", "),
      late: list.some((p) => p.late),
      earlyLeave: list.some((p) => p.earlyLeave),
      punches: list.length,
      absent: false,
    });
  }
  return {
    days,
    summary: {
      present: days.filter((d) => !d.absent).length,
      late: days.filter((d) => d.late).length,
      earlyLeave: days.filter((d) => d.earlyLeave).length,
      punches: days.reduce((s, d) => s + d.punches, 0),
      absent: days.filter((d) => d.absent).length,
    },
  };
}

export type ReportResponseDecision = { status: 200 } | { status: 413; error: string };

/** A truncated load would yield wrong absences, so refuse rather than render an incomplete PDF. */
export function decideReportResponse(load: { truncated: boolean }): ReportResponseDecision {
  return load.truncated
    ? {
        status: 413,
        error: `This person has more than ${PERSON_REPORT_PUNCH_CAP} punches in the range - choose a narrower date range`,
      }
    : { status: 200 };
}
