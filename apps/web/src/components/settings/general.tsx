"use client";

import { useState, useTransition } from "react";
import type { AppSettings } from "@hrm/shared";
import { saveAppSettings } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appSettingsSchema } from "@/lib/settings-schemas";
import { Field, FormMessage, fieldErrors } from "./shared";

// Index = JavaScript getUTCDay() value (0 = Sunday).
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] as const;

export function GeneralSettings({ initial }: { initial: AppSettings }) {
  const [v, setV] = useState(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    setOk(null);
    const parsed = appSettingsSchema.safeParse(v);
    if (!parsed.success) return setErrors(fieldErrors(parsed.error.issues));
    setErrors({});
    start(async () => {
      try {
        const r = await saveAppSettings(v);
        if (r.ok) setOk("Saved.");
        else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not save");
      }
    });
  }

  return (
    <form onSubmit={submit} className="max-w-md space-y-4" noValidate>
      <Field label="Organisation name" error={errors.orgName}>
        {(p) => <Input {...p} value={v.orgName} onChange={(e) => setV({ ...v, orgName: e.target.value })} />}
      </Field>
      <Field
        label="Time zone"
        help="IANA name, e.g. Asia/Dhaka. Attendance dates and SMS times follow this zone."
        error={errors.timeZone}
      >
        {(p) => <Input {...p} value={v.timeZone} onChange={(e) => setV({ ...v, timeZone: e.target.value })} />}
      </Field>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Weekend days</legend>
        <p className="text-xs text-muted-foreground">
          Closed days of the week. The person PDF report counts a day as absent only if it is not a weekend day or a
          holiday.
        </p>
        <div className="flex flex-wrap gap-3">
          {WEEKDAYS.map((label, day) => (
            <label key={label} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={v.weekendDays.includes(day)}
                onChange={(e) =>
                  setV({
                    ...v,
                    weekendDays: e.target.checked
                      ? [...v.weekendDays.filter((d) => d !== day), day].sort((a, b) => a - b)
                      : v.weekendDays.filter((d) => d !== day),
                  })
                }
              />
              {label}
            </label>
          ))}
        </div>
        {errors.weekendDays ? (
          <p role="alert" className="text-xs text-destructive">
            {errors.weekendDays}
          </p>
        ) : null}
      </fieldset>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={v.notificationSound}
          onChange={(e) => setV({ ...v, notificationSound: e.target.checked })}
        />
        Play a sound for new punches on the dashboard
      </label>
      <FormMessage error={serverError} ok={ok} />
      <Button type="submit" disabled={pending}>
        {pending ? "Saving..." : "Save"}
      </Button>
    </form>
  );
}
