"use client";

import { useState, useTransition } from "react";
import { SmsSettingsSchema, type SmsSettings } from "@hrm/shared";
import { saveSmsSettings } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { allowedPlaceholders, previewTemplate, type TemplateField } from "@/lib/sms-preview";
import { Field, FormMessage, fieldErrors, textareaClass } from "./shared";

const TEMPLATES: { key: TemplateField; label: string }[] = [
  { key: "normalTemplate", label: "On-time punch" },
  { key: "lateTemplate", label: "Late punch" },
  { key: "earlyLeaveTemplate", label: "Early leave" },
  { key: "absentTemplate", label: "Absent student" },
  { key: "summaryTemplate", label: "Daily summary" },
];

const TOGGLES: { key: "smsEnabled" | "earlyLeaveEnabled" | "absentEnabled" | "summaryEnabled"; label: string }[] = [
  { key: "smsEnabled", label: "Send punch SMS to guardians" },
  { key: "earlyLeaveEnabled", label: "Send early-leave SMS" },
  { key: "absentEnabled", label: "Send absent SMS" },
  { key: "summaryEnabled", label: "Send daily summary to admin phones" },
];

export function SmsTemplates({ initial }: { initial: SmsSettings }) {
  const [v, setV] = useState<SmsSettings>(initial);
  const [phones, setPhones] = useState<[string, string]>([initial.adminPhones[0] ?? "", initial.adminPhones[1] ?? ""]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    setOk(null);
    const value = { ...v, adminPhones: phones.map((p) => p.trim()).filter(Boolean) };
    const parsed = SmsSettingsSchema.safeParse(value);
    if (!parsed.success) return setErrors(fieldErrors(parsed.error.issues));
    setErrors({});
    start(async () => {
      try {
        const r = await saveSmsSettings(parsed.data);
        if (r.ok) setOk("Saved.");
        else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not save");
      }
    });
  }

  return (
    <form onSubmit={submit} noValidate className="max-w-3xl space-y-6">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Sending</legend>
        {TOGGLES.map((t) => (
          <label key={t.key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={v[t.key]} onChange={(e) => setV({ ...v, [t.key]: e.target.checked })} />
            {t.label}
          </label>
        ))}
      </fieldset>

      {TEMPLATES.map((t) => {
        const preview = previewTemplate(t.key, v[t.key]);
        const inline =
          preview.unknown.length > 0
            ? `Unknown placeholder ${preview.unknown.join(", ")}. Allowed: ${allowedPlaceholders(t.key).join(" ")}`
            : (errors[t.key] ?? null);
        return (
          <div key={t.key} className="space-y-1">
            <Field label={`${t.label} template`} help={`Placeholders: ${allowedPlaceholders(t.key).join(" ")}`} error={inline}>
              {(p) => (
                <textarea
                  {...p}
                  rows={2}
                  className={textareaClass}
                  value={v[t.key]}
                  onChange={(e) => setV({ ...v, [t.key]: e.target.value })}
                />
              )}
            </Field>
            <p className="text-xs text-muted-foreground">
              Preview: <span className="rounded bg-accent px-1 py-0.5 text-accent-foreground">{preview.text || "(empty)"}</span>
            </p>
          </div>
        );
      })}

      <Field label="Daily summary time (HH:mm)" error={errors.summaryTime}>
        {(p) => (
          <Input {...p} className="w-32" placeholder="16:00" value={v.summaryTime} onChange={(e) => setV({ ...v, summaryTime: e.target.value })} />
        )}
      </Field>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-medium">Admin phones (receive the summary, max 2)</legend>
        {([0, 1] as const).map((i) => (
          <Field key={i} label={`Admin phone ${i + 1}`} error={i === 0 ? errors.adminPhones : null}>
            {(p) => (
              <Input
                {...p}
                type="tel"
                value={phones[i]}
                onChange={(e) => setPhones((cur) => (i === 0 ? [e.target.value, cur[1]] : [cur[0], e.target.value]))}
              />
            )}
          </Field>
        ))}
      </fieldset>

      <FormMessage error={serverError} ok={ok} />
      <Button type="submit" disabled={pending}>
        {pending ? "Saving..." : "Save"}
      </Button>
    </form>
  );
}
