import type { Attendance, Person } from "@hrm/shared";
import { formatTimeInZone } from "@/lib/org-time";

const badge = "ml-1 rounded px-1.5 py-0.5 text-xs font-medium";

export function LogsTable({
  rows,
  people,
  timeZone,
}: {
  rows: Attendance[];
  people: ReadonlyMap<string, Person>;
  timeZone: string;
}) {
  if (rows.length === 0) {
    return <p className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">No attendance records match these filters.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Attendance logs, newest first</caption>
        <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Date</th>
            <th scope="col" className="px-3 py-2">Time</th>
            <th scope="col" className="px-3 py-2">Person</th>
            <th scope="col" className="px-3 py-2">Direction</th>
            <th scope="col" className="px-3 py-2">Flags</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const person = people.get(p.personId);
            return (
              <tr key={`${p.personId}-${p.ts.getTime()}-${p.direction}`} className="border-t border-border">
                <td className="px-3 py-2 whitespace-nowrap">{p.date}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatTimeInZone(timeZone, p.ts)}</td>
                <td className="px-3 py-2">
                  {person?.name ?? <span className="text-muted-foreground">Unknown</span>}{" "}
                  <span className="text-muted-foreground">({p.personId})</span>
                </td>
                <td className="px-3 py-2">{p.direction === "in" ? "In" : "Out"}</td>
                <td className="px-3 py-2">
                  {p.late ? <span className={`${badge} bg-amber-100 text-amber-900`}>Late</span> : null}
                  {p.earlyLeave ? <span className={`${badge} bg-orange-100 text-orange-900`}>Early leave</span> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
