"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import type { DailyStat } from "@/lib/stats";

type Mode = "bar" | "line";

export function AttendanceChart({ rows }: { rows: DailyStat[] }) {
  const [mode, setMode] = useState<Mode>("bar");
  // noData days become null so lines break (gaps) and bars are empty.
  const data = rows.map((r) => ({
    date: r.date.slice(5),
    present: r.noData ? null : r.present,
    absent: r.noData ? null : r.absent,
    punches: r.noData ? null : r.punches,
    late: r.noData ? null : r.late,
  }));
  const summary = `${mode === "bar" ? "Present versus absent" : "Punches versus late"} per day, ${rows.length} days from ${rows[0]?.date ?? "-"} to ${rows[rows.length - 1]?.date ?? "-"}.`;
  return (
    <section aria-label="Attendance chart" className="space-y-3">
      <div role="group" aria-label="Chart type" className="flex gap-2">
        <Button type="button" size="sm" variant={mode === "bar" ? "default" : "outline"} aria-pressed={mode === "bar"} onClick={() => setMode("bar")}>
          Present vs absent
        </Button>
        <Button type="button" size="sm" variant={mode === "line" ? "default" : "outline"} aria-pressed={mode === "line"} onClick={() => setMode("line")}>
          Punches vs late
        </Button>
      </div>
      <div role="img" aria-label={summary} className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {mode === "bar" ? (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey="present" name="Present" fill="#15803d" />
              <Bar dataKey="absent" name="Absent" fill="#b91c1c" />
            </BarChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="punches" name="Punches" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
              <Line type="monotone" dataKey="late" name="Late" stroke="#b45309" strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3, strokeWidth: 2 }} connectNulls={false} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Daily attendance statistics</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Present</th>
            <th scope="col">Absent</th>
            <th scope="col">Late</th>
            <th scope="col">Punches</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.date}>
              <th scope="row">{r.date}</th>
              {r.noData ? (
                <td colSpan={4}>No data</td>
              ) : (
                <>
                  <td>{r.present}</td>
                  <td>{r.absent}</td>
                  <td>{r.late}</td>
                  <td>{r.punches}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
