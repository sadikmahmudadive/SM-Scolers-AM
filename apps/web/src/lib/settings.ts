import { BridgeSettingsSchema, COLLECTIONS, HolidaySchema, PersonSchema, SmsSettingsSchema } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";
import { PERSON_ID_PATTERN } from "./csv";
import {
  appSettingsSchema,
  deviceBackupSchema,
  deviceInputSchema,
  holidayInputSchema,
  ID_PATTERN,
  isRealDate,
  scheduleInputSchema,
} from "./settings-schemas";

export const MAX_BACKUP_BYTES = 5 * 1024 * 1024;
const BATCH_SIZE = 400;
const MAX_PROBLEMS = 10;
const BACKUP_VERSION = 1;

export type SettingsDeps = {
  newId: () => string;
  set: (collection: string, id: string, data: Record<string, unknown>, opts?: { merge?: boolean }) => Promise<void>;
  remove: (collection: string, id: string) => Promise<void>;
  get: (collection: string, id: string) => Promise<Record<string, unknown> | null>;
  /** Timestamps must already be converted to Date. */
  list: (collection: string) => Promise<{ id: string; data: Record<string, unknown> }[]>;
  /** One atomic batch of full-overwrite sets (the caller keeps it at or under 400). */
  setBatch: (items: { collection: string; id: string; data: Record<string, unknown> }[]) => Promise<void>;
};

export type Result = { ok: true } | { ok: false; error: string };
export type RestoreResult = { ok: true; restored: Record<string, number> } | { ok: false; error: string };

function assertAdmin(caller: Session | null): void {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
}

function message(e: z.ZodError): string {
  const i = e.issues[0];
  if (!i) return "Invalid input";
  const path = i.path.join(".");
  return path ? `${path}: ${i.message}` : i.message;
}

const idCheck = (id: unknown): id is string => typeof id === "string" && ID_PATTERN.test(id);

export type ScheduleInput = z.input<typeof scheduleInputSchema> & { id?: string };

export async function saveScheduleWith(deps: SettingsDeps, caller: Session | null, input: ScheduleInput): Promise<Result> {
  assertAdmin(caller);
  const { id: givenId, ...rest } = input;
  if (givenId !== undefined && !idCheck(givenId)) return { ok: false, error: "Invalid schedule ID" };
  const parsed = scheduleInputSchema.safeParse(rest);
  if (!parsed.success) return { ok: false, error: message(parsed.error) };
  const data: Record<string, unknown> = { ...parsed.data };
  if (data.dismissal === undefined) delete data.dismissal;
  await deps.set(COLLECTIONS.schedules, givenId ?? deps.newId(), data);
  return { ok: true };
}

export async function deleteScheduleWith(deps: SettingsDeps, caller: Session | null, id: string): Promise<Result> {
  assertAdmin(caller);
  if (!idCheck(id)) return { ok: false, error: "Invalid schedule ID" };
  await deps.remove(COLLECTIONS.schedules, id);
  return { ok: true };
}

export async function addHolidayWith(
  deps: SettingsDeps,
  caller: Session | null,
  date: string,
  name: string,
): Promise<Result> {
  assertAdmin(caller);
  const parsed = holidayInputSchema.safeParse({ date, name });
  if (!parsed.success) return { ok: false, error: message(parsed.error) };
  await deps.set(COLLECTIONS.holidays, parsed.data.date, { name: parsed.data.name });
  return { ok: true };
}

export async function removeHolidayWith(deps: SettingsDeps, caller: Session | null, date: string): Promise<Result> {
  assertAdmin(caller);
  if (!isRealDate(date)) return { ok: false, error: "Invalid date" };
  await deps.remove(COLLECTIONS.holidays, date);
  return { ok: true };
}

async function saveSettingsDoc(
  deps: SettingsDeps,
  caller: Session | null,
  docId: "bridge" | "sms" | "app",
  schema: z.ZodType<Record<string, unknown>>,
  input: unknown,
): Promise<Result> {
  assertAdmin(caller);
  const parsed = schema.safeParse(input);
  if (!parsed.success) return { ok: false, error: message(parsed.error) };
  await deps.set(COLLECTIONS.settings, docId, parsed.data);
  return { ok: true };
}

export const saveSmsSettingsWith = (deps: SettingsDeps, caller: Session | null, input: unknown) =>
  saveSettingsDoc(deps, caller, "sms", SmsSettingsSchema, input);
export const saveBridgeSettingsWith = (deps: SettingsDeps, caller: Session | null, input: unknown) =>
  saveSettingsDoc(deps, caller, "bridge", BridgeSettingsSchema, input);
export const saveAppSettingsWith = (deps: SettingsDeps, caller: Session | null, input: unknown) =>
  saveSettingsDoc(deps, caller, "app", appSettingsSchema, input);

export type DeviceInput = { id: string; name: string; ip: string; port: number };

export async function saveDeviceWith(deps: SettingsDeps, caller: Session | null, input: DeviceInput): Promise<Result> {
  assertAdmin(caller);
  if (!idCheck(input.id)) return { ok: false, error: "Device ID must be letters, digits, - or _" };
  const parsed = deviceInputSchema.safeParse({ name: input.name, ip: input.ip, port: input.port });
  if (!parsed.success) return { ok: false, error: message(parsed.error) };
  // merge: the bridge owns lastSeen, which must survive an edit.
  await deps.set(COLLECTIONS.devices, input.id, parsed.data, { merge: true });
  return { ok: true };
}

export async function deleteDeviceWith(deps: SettingsDeps, caller: Session | null, id: string): Promise<Result> {
  assertAdmin(caller);
  if (!idCheck(id)) return { ok: false, error: "Invalid device ID" };
  await deps.remove(COLLECTIONS.devices, id);
  return { ok: true };
}

// ---------------------------------------------------------------- backup

const SETTINGS_DOCS = ["bridge", "sms", "app"] as const;

function serialize(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) out[k] = v instanceof Date ? v.toISOString() : v;
  return out;
}

export async function exportBackupWith(deps: SettingsDeps, caller: Session | null): Promise<string> {
  assertAdmin(caller);
  const rows = async (c: string) =>
    (await deps.list(c))
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((r) => ({ id: r.id, ...serialize(r.data) }));
  const settings: Record<string, unknown> = {};
  for (const name of SETTINGS_DOCS) {
    const doc = await deps.get(COLLECTIONS.settings, name);
    if (doc) settings[name] = serialize(doc);
  }
  return JSON.stringify({
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    people: await rows(COLLECTIONS.people),
    schedules: await rows(COLLECTIONS.schedules),
    holidays: await rows(COLLECTIONS.holidays),
    devices: await rows(COLLECTIONS.devices),
    settings,
  });
}

const docList = z.array(z.record(z.string(), z.unknown())).optional();
const envelope = z.object({
  version: z.number(),
  people: docList,
  schedules: docList,
  holidays: docList,
  devices: docList,
  settings: z.record(z.string(), z.unknown()).optional(),
});

function toDate(v: unknown): unknown {
  if (typeof v !== "string") return v;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d;
}

type Write = { collection: string; id: string; data: Record<string, unknown> };
type AnySchema = z.ZodType<Record<string, unknown>>;

export async function restoreBackupWith(
  deps: SettingsDeps,
  caller: Session | null,
  json: string,
): Promise<RestoreResult> {
  assertAdmin(caller);
  if (typeof json !== "string" || Buffer.byteLength(json, "utf8") > MAX_BACKUP_BYTES) {
    return { ok: false, error: `Backup file is too large (max ${MAX_BACKUP_BYTES / 1024 / 1024} MB)` };
  }
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    return { ok: false, error: "Not a valid JSON file" };
  }
  const env = envelope.safeParse(raw);
  if (!env.success) return { ok: false, error: `Not a backup file: ${message(env.error)}` };
  if (env.data.version !== BACKUP_VERSION) {
    return { ok: false, error: `Unsupported backup version ${env.data.version} (expected ${BACKUP_VERSION})` };
  }

  const writes: Write[] = [];
  const problems: string[] = [];
  const counts: Record<string, number> = { people: 0, schedules: 0, holidays: 0, devices: 0, settings: 0 };
  const note = (c: string, id: string, msg: string) => problems.push(`${c}/${id}: ${msg}`);

  const validated = (schema: AnySchema, dates: string[] = []) => (rest: Record<string, unknown>) => {
    const input = { ...rest };
    for (const k of dates) if (k in input) input[k] = toDate(input[k]);
    const r = schema.safeParse(input);
    return r.success ? r.data : message(r.error);
  };

  const each = (
    collection: string,
    docs: Record<string, unknown>[] | undefined,
    validate: (id: string, rest: Record<string, unknown>) => Record<string, unknown> | string,
  ) => {
    for (const doc of docs ?? []) {
      const { id, ...rest } = doc;
      if (typeof id !== "string" || id === "") {
        note(collection, "(missing id)", "document id is required");
        continue;
      }
      const out = validate(id, rest);
      if (typeof out === "string") note(collection, id, out);
      else {
        writes.push({ collection, id, data: out });
        counts[collection] = (counts[collection] ?? 0) + 1;
      }
    }
  };

  const personV = validated(PersonSchema, ["createdAt"]);
  const scheduleV = validated(scheduleInputSchema as unknown as AnySchema);
  const holidayV = validated(HolidaySchema);
  const deviceV = validated(deviceBackupSchema, ["lastSeen"]);

  each("people", env.data.people, (id, rest) =>
    PERSON_ID_PATTERN.test(id) ? personV(rest) : "invalid person ID",
  );
  each("schedules", env.data.schedules, (id, rest) => (idCheck(id) ? scheduleV(rest) : "invalid schedule ID"));
  each("holidays", env.data.holidays, (id, rest) =>
    isRealDate(id) ? holidayV(rest) : "holiday ID must be a real yyyy-MM-dd date",
  );
  each("devices", env.data.devices, (id, rest) => (idCheck(id) ? deviceV(rest) : "invalid device ID"));

  const settings = env.data.settings ?? {};
  const settingsSchemas: Record<(typeof SETTINGS_DOCS)[number], AnySchema> = {
    bridge: BridgeSettingsSchema,
    sms: SmsSettingsSchema,
    app: appSettingsSchema,
  };
  for (const key of Object.keys(settings)) {
    if (!(SETTINGS_DOCS as readonly string[]).includes(key)) note("settings", key, "unknown settings document");
  }
  for (const name of SETTINGS_DOCS) {
    if (!(name in settings)) continue;
    const v = settings[name];
    if (typeof v !== "object" || v === null || Array.isArray(v)) {
      note("settings", name, "must be an object");
      continue;
    }
    const r = settingsSchemas[name].safeParse(v);
    if (!r.success) note("settings", name, message(r.error));
    else {
      writes.push({ collection: COLLECTIONS.settings, id: name, data: r.data });
      counts.settings = (counts.settings ?? 0) + 1;
    }
  }

  if (problems.length > 0) {
    const shown = problems.slice(0, MAX_PROBLEMS);
    const more = problems.length > shown.length ? `\n...and ${problems.length - shown.length} more` : "";
    return {
      ok: false,
      error: `Backup rejected, nothing was written. ${problems.length} problem(s):\n${shown.join("\n")}${more}`,
    };
  }

  for (let i = 0; i < writes.length; i += BATCH_SIZE) await deps.setBatch(writes.slice(i, i + BATCH_SIZE));
  return { ok: true, restored: counts };
}
