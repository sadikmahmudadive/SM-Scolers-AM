import type { Attendance } from "@hrm/shared";
import { summarizeToday } from "./attendance-queries";

export type Kpis = { totalPeople: number; present: number; late: number; smsSent: number };

/** `punches` must already be today's punches (the live query is date == today). */
export function computeKpis(
  people: readonly { id: string; active: boolean }[],
  punches: readonly Pick<Attendance, "personId" | "late">[],
  smsToday: readonly { status: string }[],
): Kpis {
  const DAY = "today";
  const s = summarizeToday(
    people,
    punches.map((p) => ({ personId: p.personId, late: p.late, date: DAY })),
    [],
    DAY,
  );
  return {
    totalPeople: people.filter((p) => p.active).length,
    present: s.present.length,
    late: s.late.length,
    smsSent: smsToday.filter((m) => m.status === "sent").length,
  };
}

export function latestPunches<T extends { ts: Date }>(punches: readonly T[], n: number): T[] {
  return [...punches].sort((a, b) => b.ts.getTime() - a.ts.getTime()).slice(0, Math.max(0, n));
}
