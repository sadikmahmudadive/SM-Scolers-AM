"use server";

import { exportAttendanceCsvWith } from "@/lib/attendance-export";
import { loadLogs, loadTimeZone } from "@/lib/attendance-loader";
import type { LogFilters } from "@/lib/attendance-queries";
import { getSession } from "@/lib/session";

export async function exportAttendanceCsv(filters: LogFilters): Promise<string> {
  return exportAttendanceCsvWith({ load: loadLogs, timeZone: loadTimeZone }, await getSession(), filters);
}
