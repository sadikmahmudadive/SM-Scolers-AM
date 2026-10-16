import type { Attendance, Person } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";
import { filterAndPage, type LogFilters } from "./attendance-queries";
import { PERSON_KINDS } from "./csv";
import { toCsv } from "./csv-export";
import { formatTimeInZone } from "./org-time";

export type AttendanceExportDeps = {
  load: (
    filters: LogFilters,
  ) => Promise<{ people: Map<string, Person>; punches: Attendance[]; truncated: boolean }>;
  timeZone: () => Promise<string>;
};

const dateStr = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const logFiltersSchema = z.object({
  from: dateStr,
  to: dateStr,
  personId: z.string().max(64).optional(),
  kind: z.enum(PERSON_KINDS).optional(),
  className: z.string().max(64).optional(),
});

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
  rawFilters: LogFilters,
): Promise<{ csv: string; truncated: boolean }> {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
  const filters = logFiltersSchema.parse(rawFilters);
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
  return { csv: toCsv(EXPORT_HEADER, rows), truncated };
}
