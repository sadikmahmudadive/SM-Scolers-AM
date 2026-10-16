"use client";

import { useState, useTransition } from "react";
import { BridgeSettingsSchema, type BridgeSettings } from "@hrm/shared";
import { saveBridgeSettings } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FormMessage, fieldErrors } from "./shared";

type Draft = Record<keyof BridgeSettings, string>;

function toDraft(s: BridgeSettings): Draft {
  return {
    pollIntervalSec: String(s.pollIntervalSec),
    zkTimeoutSec: String(s.zkTimeoutSec),
    gsmPort: s.gsmPort,
    gsmBaud: String(s.gsmBaud),
    staleSmsWindowMin: String(s.staleSmsWindowMin),
    ussdCode: s.ussdCode,
  };
}

const WHOLE = "Enter a whole number of at least 1";

export function BridgeSettingsForm({ initial }: { initial: BridgeSettings }) {
  const [d, setD] = useState<Draft>(toDraft(initial));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const num = (k: keyof Draft) => (d[k].trim() === "" ? Number.NaN : Number(d[k]));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    setOk(null);
    const value = {
      pollIntervalSec: num("pollIntervalSec"),
      zkTimeoutSec: num("zkTimeoutSec"),
      gsmPort: d.gsmPort.trim(),
      gsmBaud: num("gsmBaud"),
      staleSmsWindowMin: num("staleSmsWindowMin"),
      ussdCode: d.ussdCode.trim(),
    };
    const parsed = BridgeSettingsSchema.safeParse(value);
    if (!parsed.success) {
      const errs = fieldErrors(parsed.error.issues);
      for (const k of Object.keys(errs)) errs[k] = k === "gsmPort" || k === "ussdCode" ? "Invalid value" : WHOLE;
      return setErrors(errs);
    }
    setErrors({});
    start(async () => {
      try {
        const r = await saveBridgeSettings(parsed.data);
        if (r.ok) setOk("Saved. The bridge picks changes up on its next poll.");
        else setServerError(r.error);
      } catch (err) {
        setServerError(err instanceof Error ? err.message : "Could not save");
      }
    });
  }

  const set = (k: keyof Draft) => (e: React.ChangeEvent<HTMLInputElement>) => setD({ ...d, [k]: e.target.value });

  return (
    <form onSubmit={submit} className="grid max-w-2xl gap-4 sm:grid-cols-2" noValidate>
      <Field
        label="Poll interval (seconds)"
        help="How often the bridge reads punches from the device."
        error={errors.pollIntervalSec}
      >
        {(p) => <Input {...p} inputMode="numeric" value={d.pollIntervalSec} onChange={set("pollIntervalSec")} />}
      </Field>
      <Field
        label="Device timeout (seconds)"
        help="How long to wait for the attendance terminal to answer."
        error={errors.zkTimeoutSec}
      >
        {(p) => <Input {...p} inputMode="numeric" value={d.zkTimeoutSec} onChange={set("zkTimeoutSec")} />}
      </Field>
      <Field
        label="GSM modem port"
        help="Serial port of the SMS modem, e.g. COM3 or /dev/ttyUSB0."
        error={errors.gsmPort}
      >
        {(p) => <Input {...p} value={d.gsmPort} onChange={set("gsmPort")} />}
      </Field>
      <Field label="GSM baud rate" help="Usually 9600 or 115200." error={errors.gsmBaud}>
        {(p) => <Input {...p} inputMode="numeric" value={d.gsmBaud} onChange={set("gsmBaud")} />}
      </Field>
      <Field
        label="Stale SMS window (minutes)"
        help="If the bridge was offline and a punch is older than this when it comes back, its SMS is skipped instead of sent late."
        error={errors.staleSmsWindowMin}
      >
        {(p) => <Input {...p} inputMode="numeric" value={d.staleSmsWindowMin} onChange={set("staleSmsWindowMin")} />}
      </Field>
      <Field label="Balance USSD code" help="Dialled by Check balance in GSM tools, e.g. *124#." error={errors.ussdCode}>
        {(p) => <Input {...p} value={d.ussdCode} onChange={set("ussdCode")} />}
      </Field>
      <div className="space-y-2 sm:col-span-2">
        <FormMessage error={serverError} ok={ok} />
        <Button type="submit" disabled={pending}>
          {pending ? "Saving..." : "Save"}
        </Button>
      </div>
    </form>
  );
}
