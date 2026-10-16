"use client";

import { useState, useTransition } from "react";
import { deleteSchedule, saveSchedule } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { scheduleInputSchema } from "@/lib/settings-schemas";
import { Field, FormMessage, fieldErrors } from "./shared";

export type ScheduleRow = {
  id: string;
  name: string;
  start: string;
  end: string;
  graceMin: number;
  dismissal?: string;
  appliesTo: string[];
};

type Draft = { id?: string; name: string; start: string; end: string; graceMin: string; dismissal: string; appliesTo: string };

const EMPTY: Draft = { name: "", start: "07:45", end: "08:15", graceMin: "0", dismissal: "", appliesTo: "" };

export function Schedules({ schedules, targets }: { schedules: ScheduleRow[]; targets: string[] }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function edit(s: ScheduleRow) {
    setErrors({});
    setServerError(null);
    setOk(null);
    setDraft({
      id: s.id,
      name: s.name,
      start: s.start,
      end: s.end,
      graceMin: String(s.graceMin),
      dismissal: s.dismissal ?? "",
      appliesTo: s.appliesTo.join(", "),
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setServerError(null);
    setOk(null);
    const input = {
      id: draft.id,
      name: draft.name,
      start: draft.start,
      end: draft.end,
      graceMin: draft.graceMin.trim() === "" ? Number.NaN : Number(draft.graceMin),
      dismissal: draft.dismissal,
      appliesTo: draft.appliesTo.split(","),
    };
    const parsed = scheduleInputSchema.safeParse(input);
    if (!parsed.success) return setErrors(fieldErrors(parsed.error.issues));
    setErrors({});
    start(async () => {
      try {
        const r = await saveSchedule(input);
        if (r.ok) {
          setOk("Schedule saved.");
          setDraft(null);
        } else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not save");
      }
    });
  }

  function remove(id: string) {
    setServerError(null);
    setOk(null);
    start(async () => {
      try {
        const r = await deleteSchedule(id);
        if (r.ok) setOk("Schedule deleted.");
        else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not delete");
      }
      setConfirmId(null);
    });
  }

  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDraft((d) => (d ? { ...d, [k]: e.target.value } : d));

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        A schedule sets the arrival window (start to end), a grace period and an optional dismissal time for the classes
        or departments it applies to.
      </p>
      <FormMessage error={draft ? null : serverError} ok={ok} />
      {schedules.length === 0 ? (
        <p className="text-sm text-muted-foreground">No schedules yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Schedules</caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="py-2 pr-4">Name</th>
                <th scope="col" className="py-2 pr-4">Arrival</th>
                <th scope="col" className="py-2 pr-4">Grace</th>
                <th scope="col" className="py-2 pr-4">Dismissal</th>
                <th scope="col" className="py-2 pr-4">Applies to</th>
                <th scope="col" className="py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} className="border-b border-border">
                  <td className="py-2 pr-4">{s.name}</td>
                  <td className="py-2 pr-4">{s.start} - {s.end}</td>
                  <td className="py-2 pr-4">{s.graceMin} min</td>
                  <td className="py-2 pr-4">{s.dismissal ?? "-"}</td>
                  <td className="py-2 pr-4">{s.appliesTo.join(", ")}</td>
                  <td className="space-x-2 py-2 whitespace-nowrap">
                    {confirmId === s.id ? (
                      <>
                        <span className="text-xs">Delete {s.name}?</span>
                        <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => remove(s.id)}>
                          Confirm delete
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button type="button" size="sm" variant="outline" onClick={() => edit(s)}>
                          Edit<span className="sr-only"> {s.name}</span>
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmId(s.id)}>
                          Delete<span className="sr-only"> {s.name}</span>
                        </Button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {draft ? (
        <form onSubmit={submit} noValidate aria-label={draft.id ? "Edit schedule" : "New schedule"} className="grid max-w-2xl gap-4 rounded-md border border-border p-4 sm:grid-cols-2">
          <Field label="Name" error={errors.name}>
            {(p) => <Input {...p} value={draft.name} onChange={set("name")} />}
          </Field>
          <Field label="Grace period (minutes)" help="Minutes after the arrival window ends before a punch counts as late." error={errors.graceMin}>
            {(p) => <Input {...p} inputMode="numeric" value={draft.graceMin} onChange={set("graceMin")} />}
          </Field>
          <Field label="Arrival start (HH:mm)" error={errors.start}>
            {(p) => <Input {...p} placeholder="07:45" value={draft.start} onChange={set("start")} />}
          </Field>
          <Field label="Arrival end (HH:mm)" error={errors.end}>
            {(p) => <Input {...p} placeholder="08:15" value={draft.end} onChange={set("end")} />}
          </Field>
          <Field label="Dismissal (HH:mm, optional)" help="Leaving before this counts as early leave." error={errors.dismissal}>
            {(p) => <Input {...p} placeholder="13:00" value={draft.dismissal} onChange={set("dismissal")} />}
          </Field>
          <Field
            label="Applies to"
            help={`Comma-separated class names or department IDs.${targets.length ? ` Known: ${targets.join(", ")}` : ""}`}
            error={errors.appliesTo}
          >
            {(p) => <Input {...p} value={draft.appliesTo} onChange={set("appliesTo")} />}
          </Field>
          <div className="space-y-2 sm:col-span-2">
            <FormMessage error={serverError} />
            <div className="flex gap-2">
              <Button type="submit" disabled={pending}>{pending ? "Saving..." : "Save schedule"}</Button>
              <Button type="button" variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </div>
        </form>
      ) : (
        <Button type="button" onClick={() => { setErrors({}); setServerError(null); setDraft(EMPTY); }}>
          Add schedule
        </Button>
      )}
    </div>
  );
}
