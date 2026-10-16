import { formatTimeInZone } from "@/lib/org-time";

export type FeedPunch = {
  id: string;
  personId: string;
  ts: Date;
  direction: "in" | "out";
  late: boolean;
  earlyLeave: boolean;
};

const badge = "rounded px-1.5 py-0.5 text-xs font-medium";

export function LiveFeed({
  punches,
  names,
  tz,
}: {
  punches: FeedPunch[];
  names: ReadonlyMap<string, string>;
  tz: string;
}) {
  if (punches.length === 0) {
    return <p className="rounded-md border border-border p-4 text-sm text-muted-foreground">No punches yet today.</p>;
  }
  return (
    <ul className="divide-y divide-border rounded-md border border-border text-sm">
      {punches.map((p) => (
        <li key={p.id} className="flex items-center gap-3 px-3 py-2">
          <time dateTime={p.ts.toISOString()} className="w-12 tabular-nums text-muted-foreground">
            {formatTimeInZone(tz, p.ts)}
          </time>
          <span className="flex-1 truncate">{names.get(p.personId) ?? p.personId}</span>
          <span className={`${badge} ${p.direction === "in" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-800"}`}>
            {p.direction === "in" ? "In" : "Out"}
          </span>
          {p.late ? <span className={`${badge} bg-amber-100 text-amber-900`}>Late</span> : null}
          {p.earlyLeave ? <span className={`${badge} bg-orange-100 text-orange-900`}>Early</span> : null}
        </li>
      ))}
    </ul>
  );
}
