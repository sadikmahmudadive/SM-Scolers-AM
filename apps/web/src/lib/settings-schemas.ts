import { AppSettingsSchema, DeviceSchema, ScheduleSchema } from "@hrm/shared";
import { z } from "zod";

export const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/** True for a real calendar date written yyyy-MM-dd (rejects 2026-02-30). */
export function isRealDate(s: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

const IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
const HOSTNAME =
  /^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$/;
const LOOKS_LIKE_IPV4 = /^[\d.]+$/;

export function isValidHost(s: string): boolean {
  if (LOOKS_LIKE_IPV4.test(s)) return IPV4.test(s);
  return HOSTNAME.test(s);
}

const appliesTo = z
  .array(z.string())
  .transform((a) => [...new Set(a.map((x) => x.trim()).filter((x) => x !== ""))])
  .pipe(z.array(z.string()).min(1, "Choose at least one class or department"));

function minutes(t: string): number {
  return Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
}

const emptyToUndefined = (v: unknown) => (v === "" || v === null ? undefined : v);

export const scheduleInputSchema = ScheduleSchema.extend({
  name: z.string().trim().min(1, "Name is required"),
  dismissal: z.preprocess(emptyToUndefined, ScheduleSchema.shape.dismissal),
  appliesTo,
}).refine((s) => s.dismissal === undefined || minutes(s.dismissal) > minutes(s.end) + s.graceMin, {
  path: ["dismissal"],
  message: "Dismissal must be later than the end of the arrival window plus the grace period",
});

export const holidayInputSchema = z.object({
  date: z.string().refine(isRealDate, "Enter a real date (yyyy-MM-dd)"),
  name: z.string().trim().min(1, "Name is required"),
});

export const appSettingsSchema = AppSettingsSchema.extend({
  orgName: z.string().trim().min(1, "Organisation name is required"),
  timeZone: z
    .string()
    .refine(isValidTimeZone, "Unknown IANA time zone (e.g. Asia/Dhaka)")
    .transform((tz) => new Intl.DateTimeFormat(undefined, { timeZone: tz }).resolvedOptions().timeZone),
});

export const deviceInputSchema = DeviceSchema.omit({ lastSeen: true }).extend({
  name: z.string().trim().min(1, "Name is required"),
  ip: z.string().trim().refine(isValidHost, "Enter a valid IPv4 address or hostname"),
});

/** Backups tolerate a device that has never been seen (lastSeen absent). */
export const deviceBackupSchema = DeviceSchema.partial({ lastSeen: true });
