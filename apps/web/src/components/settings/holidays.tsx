"use client";

import { useState, useTransition } from "react";
import { addHoliday, removeHoliday } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { holidayInputSchema } from "@/lib/settings-schemas";
import { Field, FormMessage, fieldErrors } from "./shared";

export type HolidayRow = { date: string; name: string };

export function Holidays({ holidays }: { holidays: HolidayRow[] }) {
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [confirmDate, setConfirmDate] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    setOk(null);
    const parsed = holidayInputSchema.safeParse({ date, name });
    if (!parsed.success) return setErrors(fieldErrors(parsed.error.issues));
    setErrors({});
    start(async () => {
      try {
        const r = await addHoliday(date, name);
        if (r.ok) {
          setOk("Holiday added.");
          setDate("");
          setName("");
        } else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not add holiday");
      }
    });
  }

  function remove(d: string) {
    setServerError(null);
    setOk(null);
    start(async () => {
      try {
        const r = await removeHoliday(d);
        if (r.ok) setOk("Holiday removed.");
        else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not remove holiday");
      }
      setConfirmDate(null);
    });
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        On a holiday nobody is counted late or absent and absence SMS are not sent.
      </p>
      <form onSubmit={submit} noValidate className="flex flex-wrap items-start gap-3">
        <Field label="Date" error={errors.date}>
          {(p) => <Input {...p} type="date" className="w-44" value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Name" error={errors.name}>
          {(p) => <Input {...p} className="w-64" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <div className="pt-6">
          <Button type="submit" disabled={pending}>Add holiday</Button>
        </div>
      </form>
      <FormMessage error={serverError} ok={ok} />
      {holidays.length === 0 ? (
        <p className="text-sm text-muted-foreground">No holidays yet.</p>
      ) : (
        <ul className="max-w-xl divide-y divide-border rounded-md border border-border text-sm">
          {holidays.map((h) => (
            <li key={h.date} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <span>
                <span className="font-mono">{h.date}</span> - {h.name}
              </span>
              {confirmDate === h.date ? (
                <span className="space-x-2">
                  <span className="text-xs">Remove {h.name}?</span>
                  <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => remove(h.date)}>
                    Confirm remove
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmDate(null)}>
                    Cancel
                  </Button>
                </span>
              ) : (
                <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmDate(h.date)}>
                  Remove<span className="sr-only"> {h.name}</span>
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
