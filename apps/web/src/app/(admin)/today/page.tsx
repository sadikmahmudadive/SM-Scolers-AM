import { COLLECTIONS } from "@hrm/shared";
import { TodayBoard, type BoardPerson, type BoardPunch } from "@/components/attendance/today-board";
import { loadHolidays, loadPeopleWithIds, loadTimeZone, toAttendance } from "@/lib/attendance-loader";
import { getAdminDb } from "@/lib/firebase-admin";
import { todayInZone } from "@/lib/org-time";
import { requireRole } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function TodayPage() {
  await requireRole("admin");
  const tz = await loadTimeZone();
  const today = todayInZone(tz, new Date());
  const [people, holidays, snap] = await Promise.all([
    loadPeopleWithIds(),
    loadHolidays(),
    getAdminDb().collection(COLLECTIONS.attendance).where("date", "==", today).get(),
  ]);
  const boardPeople: BoardPerson[] = people.map((p) => ({
    id: p.id,
    name: p.name,
    kind: p.kind,
    className: p.className,
    active: p.active,
  }));
  const initialPunches: BoardPunch[] = snap.docs.map((d) => {
    const a = toAttendance(d.data());
    return { personId: a.personId, date: a.date, late: a.late };
  });
  return (
    <main className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Present today</h1>
      <TodayBoard key={today} tz={tz} people={boardPeople} holidays={holidays} today={today} initialPunches={initialPunches} />
    </main>
  );
}
