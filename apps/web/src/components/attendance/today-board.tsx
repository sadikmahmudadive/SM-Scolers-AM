"use client";

import { useEffect, useMemo, useState } from "react";
import { collection, onSnapshot, query, where } from "firebase/firestore";
import { Input } from "@/components/ui/input";
import { summarizeToday } from "@/lib/attendance-queries";
import { ensureLiveAuth, getClientDb } from "@/lib/firebase-live";

export type BoardPerson = {
  id: string;
  name: string;
  kind: string;
  className?: string;
  active: boolean;
};
export type BoardPunch = { personId: string; date: string; late: boolean };

type LiveState = "connecting" | "live" | "failed";

function List({ title, items, tone }: { title: string; items: BoardPerson[]; tone: string }) {
  return (
    <section aria-labelledby={`h-${title}`} className="rounded-md border border-border">
      <h2 id={`h-${title}`} className={`border-b border-border px-3 py-2 text-sm font-semibold ${tone}`}>
        {title} ({items.length})
      </h2>
      {items.length === 0 ? (
        <p className="p-3 text-sm text-muted-foreground">Nobody.</p>
      ) : (
        <ul className="max-h-96 divide-y divide-border overflow-y-auto text-sm">
          {items.map((p) => (
            <li key={p.id} className="px-3 py-1.5">
              {p.name} <span className="text-muted-foreground">({p.id}{p.className ? `, ${p.className}` : ""})</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function TodayBoard({
  people,
  holidays,
  today,
  initialPunches,
}: {
  people: BoardPerson[];
  holidays: string[];
  today: string;
  initialPunches: BoardPunch[];
}) {
  const [punches, setPunches] = useState<BoardPunch[]>(initialPunches);
  const [state, setState] = useState<LiveState>("connecting");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let unsub: (() => void) | undefined;
    let cancelled = false;
    ensureLiveAuth()
      .then(() => {
        if (cancelled) return;
        unsub = onSnapshot(
          query(collection(getClientDb(), "attendance"), where("date", "==", today)),
          (snap) => {
            setPunches(
              snap.docs.map((d) => {
                const x = d.data();
                return { personId: String(x.personId ?? ""), date: String(x.date ?? ""), late: x.late === true };
              }),
            );
            setState("live");
          },
          () => setState("failed"),
        );
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
      unsub?.();
    };
  }, [today]);

  const summary = useMemo(() => summarizeToday(people, punches, holidays, today), [people, punches, holidays, today]);
  const isHoliday = holidays.includes(today);
  const q = filter.trim().toLowerCase();
  const match = (p: BoardPerson) =>
    !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q) || (p.className ?? "").toLowerCase().includes(q);
  const presentOnTime = summary.present.filter((p) => !summary.late.includes(p));

  return (
    <div className="space-y-4">
      <p role="status" className="text-sm text-muted-foreground">
        {today}
        {isHoliday ? " - holiday" : ""} -{" "}
        {state === "live"
          ? "Live updates on"
          : state === "connecting"
            ? "Connecting to live updates..."
            : null}
      </p>
      {state === "failed" ? (
        <p role="alert" className="rounded-md border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
          Live updates are unavailable. Showing a snapshot from when the page loaded; reload the page to refresh.
        </p>
      ) : null}

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Present", summary.present.length],
          ["Late", summary.late.length],
          ["Absent", summary.absent.length],
          ["Total active", people.filter((p) => p.active).length],
        ].map(([label, n]) => (
          <div key={label} className="rounded-md border border-border p-3">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-2xl font-semibold">{n}</dd>
          </div>
        ))}
      </dl>

      <div>
        <label htmlFor="board-filter" className="sr-only">
          Filter by name, ID or class
        </label>
        <Input
          id="board-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name, ID or class"
          className="w-72"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <List title="Present" items={presentOnTime.filter(match)} tone="text-green-700" />
        <List title="Late" items={summary.late.filter(match)} tone="text-amber-700" />
        <List title="Absent" items={summary.absent.filter(match)} tone="text-red-700" />
      </div>
    </div>
  );
}
