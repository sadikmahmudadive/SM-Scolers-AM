import type { DayRow, DayStatus } from "@/lib/person-days";

const badge = "rounded px-1.5 py-0.5 text-xs font-medium";

const STATUS_STYLE: Record<DayStatus, { label: string; cls: string }> = {
  present: { label: "Present", cls: "bg-green-100 text-green-800" },
  late: { label: "Late", cls: "bg-amber-100 text-amber-900" },
  absent: { label: "Absent", cls: "bg-red-100 text-red-800" },
  holiday: { label: "Holiday", cls: "bg-slate-200 text-slate-800" },
};

export function StatusBadge({ status }: { status: DayStatus }) {
  const s = STATUS_STYLE[status];
  return <span className={`${badge} ${s.cls}`}>{s.label}</span>;
}

export function DayRowsTable({ rows, caption }: { rows: DayRow[]; caption: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border text-left">
            <th scope="col" className="py-1">Date</th>
            <th scope="col">First in</th>
            <th scope="col">Last out</th>
            <th scope="col">Punches</th>
            <th scope="col">Flags</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.date} className="border-b border-border">
              <td className="py-1">{r.date}</td>
              <td>{r.firstIn ?? "-"}</td>
              <td>{r.lastOut ?? "-"}</td>
              <td>{r.punches}</td>
              <td>
                {r.holiday ? <span className={`${badge} bg-slate-200 text-slate-800`}>Holiday</span> : null}
                {r.late ? <span className={`${badge} ml-1 bg-amber-100 text-amber-900`}>Late</span> : null}
                {r.earlyLeave ? <span className={`${badge} ml-1 bg-orange-100 text-orange-900`}>Early leave</span> : null}
                {!r.holiday && !r.late && !r.earlyLeave ? (r.punches === 0 ? "Absent" : "-") : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
