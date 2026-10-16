"use client";

import dynamic from "next/dynamic";
import { useState, useTransition } from "react";
import { exportStatsCsv } from "@/actions/reports";
import { Button } from "@/components/ui/button";
import type { DailyStat } from "@/lib/stats";

const AttendanceChart = dynamic(() => import("./attendance-chart").then((m) => m.AttendanceChart), {
  ssr: false,
  loading: () => <p className="text-sm text-muted-foreground">Loading chart...</p>,
});

export function StatisticsChart({ rows, range }: { rows: DailyStat[]; range: { from: string; to: string } }) {
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          onClick={() =>
            start(async () => {
              setMsg(null);
              setWarn(null);
              try {
                const result = await exportStatsCsv(range);
                const url = URL.createObjectURL(new Blob([String.fromCharCode(0xfeff), result.csv], { type: "text/csv;charset=utf-8" }));
                const a = document.createElement("a");
                a.href = url;
                a.download = `statistics_${range.from}_${range.to}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
                if (result.truncated) setWarn("Export limited to the most recent 50000 punches.");
              } catch (e) {
                setMsg(e instanceof Error ? e.message : "Export failed");
              }
            })
          }
        >
          {pending ? "Exporting..." : "Export CSV"}
        </Button>
        <span role="status" className="text-xs text-destructive">{msg}</span>
        <span role="status" className="text-xs text-amber-700">{warn}</span>
      </div>
      <AttendanceChart rows={rows} />
    </div>
  );
}
