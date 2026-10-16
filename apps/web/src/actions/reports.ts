"use server";

import { exportStatsCsvWith } from "@/lib/stats-export";
import { loadStatsData } from "@/lib/stats-loader";
import { getSession } from "@/lib/session";

export async function exportStatsCsv(range: { from: string; to: string }): Promise<{ csv: string; truncated: boolean }> {
  return exportStatsCsvWith({ load: loadStatsData }, await getSession(), range);
}
