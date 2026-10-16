"use client";

import { useState, useTransition } from "react";
import type { AppSettings } from "@hrm/shared";
import { saveAppSettings } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appSettingsSchema } from "@/lib/settings-schemas";
import { Field, FormMessage, fieldErrors } from "./shared";

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
