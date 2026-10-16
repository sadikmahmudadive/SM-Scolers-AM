"use client";

import { useState, useTransition } from "react";
import { deleteDevice, saveDevice } from "@/actions/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ID_PATTERN, deviceInputSchema } from "@/lib/settings-schemas";
import { Field, FormMessage, fieldErrors } from "./shared";

export type DeviceRow = { id: string; name: string; ip: string; port: number; lastSeen?: string };

type Draft = { id: string; name: string; ip: string; port: string; isNew: boolean };
const EMPTY: Draft = { id: "", name: "", ip: "", port: "4370", isNew: true };

export function Devices({ devices }: { devices: DeviceRow[] }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setServerError(null);
    setOk(null);
    const value = {
      name: draft.name,
      ip: draft.ip,
      port: draft.port.trim() === "" ? Number.NaN : Number(draft.port),
    };
    const parsed = deviceInputSchema.safeParse(value);
    const errs = parsed.success ? {} : fieldErrors(parsed.error.issues);
    if (!ID_PATTERN.test(draft.id)) errs.id = "Letters, digits, - and _ only (max 64)";
    if (errs.port) errs.port = "Port must be a whole number from 1 to 65535";
    if (Object.keys(errs).length > 0) return setErrors(errs);
    setErrors({});
    start(async () => {
      try {
        const r = await saveDevice({ id: draft.id, ...value });
        if (r.ok) {
          setOk("Device saved.");
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
        const r = await deleteDevice(id);
        if (r.ok) setOk("Device deleted.");
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
      <p className="text-sm text-muted-foreground">Attendance terminals the bridge polls. Last seen is updated by the bridge.</p>
      <FormMessage error={draft ? null : serverError} ok={ok} />
      {devices.length === 0 ? (
        <p className="text-sm text-muted-foreground">No devices yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Devices</caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="py-2 pr-4">ID</th>
                <th scope="col" className="py-2 pr-4">Name</th>
                <th scope="col" className="py-2 pr-4">Address</th>
                <th scope="col" className="py-2 pr-4">Last seen</th>
                <th scope="col" className="py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id} className="border-b border-border">
                  <td className="py-2 pr-4 font-mono">{d.id}</td>
                  <td className="py-2 pr-4">{d.name}</td>
                  <td className="py-2 pr-4">{d.ip}:{d.port}</td>
                  <td className="py-2 pr-4">{d.lastSeen ?? "never"}</td>
                  <td className="space-x-2 py-2 whitespace-nowrap">
                    {confirmId === d.id ? (
                      <>
                        <span className="text-xs">Delete {d.name}?</span>
                        <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => remove(d.id)}>
                          Confirm delete
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setErrors({});
                            setServerError(null);
                            setOk(null);
                            setDraft({ id: d.id, name: d.name, ip: d.ip, port: String(d.port), isNew: false });
                          }}
                        >
                          Edit<span className="sr-only"> {d.name}</span>
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmId(d.id)}>
                          Delete<span className="sr-only"> {d.name}</span>
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
        <form onSubmit={submit} noValidate aria-label={draft.isNew ? "New device" : "Edit device"} className="grid max-w-2xl gap-4 rounded-md border border-border p-4 sm:grid-cols-2">
          <Field label="Device ID" help="Short key used in attendance records, e.g. main." error={errors.id}>
            {(p) => <Input {...p} disabled={!draft.isNew} value={draft.id} onChange={set("id")} />}
          </Field>
          <Field label="Name" error={errors.name}>
            {(p) => <Input {...p} value={draft.name} onChange={set("name")} />}
          </Field>
          <Field label="IP address or hostname" error={errors.ip}>
            {(p) => <Input {...p} placeholder="192.168.1.201" value={draft.ip} onChange={set("ip")} />}
          </Field>
          <Field label="Port" error={errors.port}>
            {(p) => <Input {...p} inputMode="numeric" value={draft.port} onChange={set("port")} />}
          </Field>
          <div className="space-y-2 sm:col-span-2">
            <FormMessage error={serverError} />
            <div className="flex gap-2">
              <Button type="submit" disabled={pending}>{pending ? "Saving..." : "Save device"}</Button>
              <Button type="button" variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </div>
        </form>
      ) : (
        <Button type="button" onClick={() => { setErrors({}); setServerError(null); setDraft(EMPTY); }}>
          Add device
        </Button>
      )}
    </div>
  );
}
