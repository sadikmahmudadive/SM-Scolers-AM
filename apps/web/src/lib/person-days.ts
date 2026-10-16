import type { Attendance } from "@hrm/shared";
import { DEFAULT_TIME_ZONE, formatTimeInZone } from "./org-time";
import { eachDate, type DateRange } from "./stats";

export type DayRow = {
  date: string;
  firstIn?: string;
  lastOut?: string;
  punches: number;
  late: boolean;
  earlyLeave: boolean;
  holiday: boolean;
};

export type DayStatus = "present" | "late" | "absent" | "holiday";

/** One row per date in the inclusive range, newest first; days without punches are kept. */
export function buildDayRows(
  punches: readonly Attendance[],
  range: DateRange,
  holidays: readonly string[],
  tz: string = DEFAULT_TIME_ZONE,
): DayRow[] {
  const byDate = new Map<string, Attendance[]>();
  for (const p of punches) {
    const list = byDate.get(p.date);
    if (list) list.push(p);
    else byDate.set(p.date, [p]);
  }
  const holidaySet = new Set(holidays);
  return eachDate(range)
    .reverse()
    .map((date) => {
      const day = byDate.get(date) ?? [];
      const ins = day.filter((p) => p.direction === "in").sort((a, b) => a.ts.getTime() - b.ts.getTime());
      const outs = day.filter((p) => p.direction === "out").sort((a, b) => b.ts.getTime() - a.ts.getTime());
      const row: DayRow = {
        date,
        punches: day.length,
        late: day.some((p) => p.late),
        earlyLeave: day.some((p) => p.earlyLeave),
        holiday: holidaySet.has(date),
      };
      if (ins[0]) row.firstIn = formatTimeInZone(tz, ins[0].ts);
      if (outs[0]) row.lastOut = formatTimeInZone(tz, outs[0].ts);
      return row;
    });
}

export function todayStatus(
  punches: readonly Pick<Attendance, "date" | "late">[],
  today: string,
  isHoliday: boolean,
): DayStatus {
  const todays = punches.filter((p) => p.date === today);
  if (todays.length === 0) return isHoliday ? "holiday" : "absent";
  return todays.some((p) => p.late) ? "late" : "present";
}

/** Inclusive range of the last `n` org-local days ending at `today` (yyyy-MM-dd). */
export function lastNDays(today: string, n: number): DateRange {
  const t = Date.parse(`${today}T00:00:00Z`) - (n - 1) * 86_400_000;
  return { from: new Date(t).toISOString().slice(0, 10), to: today };
}
