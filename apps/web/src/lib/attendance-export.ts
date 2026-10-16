import type { Attendance, Person } from "@hrm/shared";
import type { Session } from "./access";
import { filterAndPage, type LogFilters } from "./attendance-queries";
import { toCsv } from "./csv-export";
import { formatTimeInZone } from "./org-time";

export type AttendanceExportDeps = {
  load: (
    filters: LogFilters,
  ) => Promise<{ people: Map<string, Person>; punches: Attendance[]; truncated: boolean }>;
  timeZone: () => Promise<string>;
};

export const EXPORT_HEADER = [
  "date",
  "time",
  "personId",
  "name",
  "kind",
  "className",
  "direction",
  "late",
  "earlyLeave",
  "status",
  "deviceId",
] as const;

export async function exportAttendanceCsvWith(
  deps: AttendanceExportDeps,
  caller: Session | null,
  filters: LogFilters,
): Promise<string> {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
  const { people, punches, truncated } = await deps.load(filters);
  const tz = await deps.timeZone();
  const all = filterAndPage(punches, people, filters, 1, Number.MAX_SAFE_INTEGER, truncated).rows;
  const rows = all.map((p) => {
    const person = people.get(p.personId);
    return [
      p.date,
      formatTimeInZone(tz, p.ts),
      p.personId,
      person?.name ?? "",
      person?.kind ?? "",
      person?.className ?? "",
      p.direction,
      p.late,
      p.earlyLeave,
      p.status,
      p.deviceId,
    ];
  });
  return toCsv(EXPORT_HEADER, rows);
}
