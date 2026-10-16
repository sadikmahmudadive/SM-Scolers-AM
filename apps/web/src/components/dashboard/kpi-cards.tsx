import type { Kpis } from "@/lib/dashboard-metrics";

export function KpiCards({ kpis }: { kpis: Kpis }) {
  const items: [string, number][] = [
    ["People", kpis.totalPeople],
    ["Present", kpis.present],
    ["Late", kpis.late],
    ["SMS sent today", kpis.smsSent],
  ];
  return (
    <dl className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map(([label, n]) => (
        <div key={label} className="rounded-md border border-border p-3">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="text-2xl font-semibold">{n}</dd>
        </div>
      ))}
    </dl>
  );
}
