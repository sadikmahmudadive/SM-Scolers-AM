"use client";

import { useState, useTransition } from "react";
import { exportAttendanceCsv } from "@/actions/exports";
import { Button } from "@/components/ui/button";
import type { LogFilters } from "@/lib/attendance-queries";

export function ExportCsvButton({ filters }: { filters: LogFilters }) {
  const [pending, start] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setMsg(null);
            setWarn(null);
            try {
              const result = await exportAttendanceCsv(filters);
              const url = URL.createObjectURL(new Blob(["\uFEFF", result.csv], { type: "text/csv;charset=utf-8" }));
              const a = document.createElement("a");
              a.href = url;
              a.download = `attendance_${filters.from}_${filters.to}.csv`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(url);
              if (result.truncated) setWarn("Export limited to the most recent 5000 rows - narrow the date range.");
            } catch (e) {
              setMsg(e instanceof Error ? e.message : "Export failed");
            }
          })
        }
      >
        {pending ? "Exporting..." : "Export CSV"}
      </Button>
      <span role="status" className="text-xs text-destructive">
        {msg}
      </span>
      <span role="status" className="text-xs text-amber-700">
        {warn}
      </span>
    </span>
  );
}
