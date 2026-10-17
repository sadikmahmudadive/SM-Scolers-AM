import { z } from "zod";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

const dateString = z.string().regex(DATE_RE, "expected yyyy-MM-dd");
const timeString = z.string().regex(TIME_RE, "expected HH:mm (00:00-23:59)");

export const SMS_PLACEHOLDERS = [
  "{id}",
  "{name}",
  "{time}",
  "{date}",
  "{status}",
  "{role}",
  "{start}",
  "{end}",
] as const;

/** Placeholders allowed in the absent-student SMS template. */
export const ABSENT_PLACEHOLDERS = ["{name}", "{id}", "{date}"] as const;

/** Placeholders allowed in the daily-summary SMS template. */
export const SUMMARY_PLACEHOLDERS = ["{date}", "{present}", "{absent}", "{late}", "{total}"] as const;

/**
 * Returns the `{token}` placeholders in a template that are not in `allowed`
 * (defaults to SMS_PLACEHOLDERS, the punch-notification set).
 */
export function findUnknownPlaceholders(
  template: string,
  allowed: readonly string[] = SMS_PLACEHOLDERS,
): string[] {
  // Doubled braces are literal text in str.format, not placeholders.
  const found = template.replace(/\{\{|\}\}/g, "").match(/\{[^{}]*\}/g) ?? [];
  return found.filter((token) => !allowed.includes(token));
}

/**
 * Structural check mirroring Python's `str.format_map` (the bridge renders templates with it):
 * a single `{` must open a `{field}` that closes before any other `{`, a single `}` must close
 * such a field, literal braces are written doubled (`{{` `}}`), and empty (`{}`) or positional
 * (`{0}`) fields are errors. Returns a human-readable message, or null when the structure is
 * valid. Whether the field NAME is allowed is checked separately by findUnknownPlaceholders.
 */
export function findTemplateSyntaxError(template: string): string | null {
  let i = 0;
  while (i < template.length) {
    const c = template[i];
    if (c === "{") {
      if (template[i + 1] === "{") {
        i += 2;
        continue;
      }
      const close = template.indexOf("}", i + 1);
      const open = template.indexOf("{", i + 1);
      if (close === -1 || (open !== -1 && open < close)) {
        return `Unclosed "{" at position ${i + 1}. Write "{{" for a literal brace.`;
      }
      const name = template.slice(i + 1, close);
      if (name === "") return `Empty placeholder "{}" at position ${i + 1}.`;
      if (/^\d+$/.test(name)) return `Positional placeholder "{${name}}" at position ${i + 1}; use a named one.`;
      i = close + 1;
      continue;
    }
    if (c === "}") {
      if (template[i + 1] === "}") {
        i += 2;
        continue;
      }
      return `Single "}" at position ${i + 1}. Write "}}" for a literal brace.`;
    }
    i += 1;
  }
  return null;
}

const templateOf = (allowed: readonly string[]) =>
  z.string().superRefine((t, ctx) => {
    const syntax = findTemplateSyntaxError(t);
    if (syntax !== null) {
      ctx.addIssue({ code: "custom", message: syntax });
      return;
    }
    if (findUnknownPlaceholders(t, allowed).length > 0) {
      ctx.addIssue({ code: "custom", message: `Unknown placeholder. Allowed: ${allowed.join(" ")}` });
    }
  });

const smsTemplate = templateOf(SMS_PLACEHOLDERS);
const absentTemplate = templateOf(ABSENT_PLACEHOLDERS);
const summaryTemplate = templateOf(SUMMARY_PLACEHOLDERS);

export const PersonSchema = z.object({
  name: z.string(),
  kind: z.enum(["staff", "teacher", "student"]),
  phone: z.string().optional(),
  fatherPhone: z.string().optional(),
  motherPhone: z.string().optional(),
  className: z.string().optional(),
  section: z.string().optional(),
  departmentId: z.string().optional(),
  managerId: z.string().optional(),
  guardianUids: z.array(z.string()).default([]),
  deviceEnrolled: z.boolean(),
  active: z.boolean(),
  createdAt: z.date(),
});
export type Person = z.infer<typeof PersonSchema>;

export const AttendanceSchema = z.object({
  personId: z.string(),
  ts: z.date(),
  date: dateString,
  status: z.string(),
  direction: z.enum(["in", "out"]),
  deviceId: z.string(),
  late: z.boolean(),
  earlyLeave: z.boolean(),
  scheduleId: z.string().optional(),
});
export type Attendance = z.infer<typeof AttendanceSchema>;

export const ScheduleSchema = z.object({
  name: z.string(),
  start: timeString,
  end: timeString,
  graceMin: z.number().int().min(0),
  dismissal: timeString.optional(),
  appliesTo: z.array(z.string()),
});
// Named ScheduleDoc: `Schedule` is already exported by ./rules (the rule-engine input shape).
export type ScheduleDoc = z.infer<typeof ScheduleSchema>;

export const HolidaySchema = z.object({
  name: z.string(),
});
export type Holiday = z.infer<typeof HolidaySchema>;

export const SmsLogSchema = z.object({
  personId: z.string(),
  phone: z.string(),
  body: z.string(),
  kind: z.enum(["normal", "late", "early", "absent", "summary", "test"]),
  status: z.enum(["sent", "failed", "skipped-stale"]),
  punchId: z.string().optional(),
  ts: z.date(),
  /** Org-local yyyy-MM-dd of `ts`; written by the bridge so "already sent today" is a bounded query. */
  date: dateString.optional(),
});
export type SmsLog = z.infer<typeof SmsLogSchema>;

export const DeviceSchema = z.object({
  name: z.string(),
  ip: z.string(),
  port: z.number().int().min(1).max(65535),
  lastSeen: z.date(),
});
export type Device = z.infer<typeof DeviceSchema>;

export const COMMAND_TYPES = [
  "test_sms",
  "ussd",
  "sync_device_users",
  "read_inbox",
  "at_command",
] as const;
export type CommandType = (typeof COMMAND_TYPES)[number];

export const CommandSchema = z.object({
  type: z.enum(COMMAND_TYPES),
  payload: z.record(z.string(), z.unknown()),
  status: z.enum(["pending", "running", "done", "error"]),
  result: z.unknown().optional(),
  createdBy: z.string().optional(),
  createdAt: z.date().optional(),
});
export type Command = z.infer<typeof CommandSchema>;

export const GSM_BAUD_RATES: readonly number[] = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200];

export const BridgeSettingsSchema = z.object({
  pollIntervalSec: z.number().int().min(1).max(3600).default(10),
  zkTimeoutSec: z.number().int().min(1).max(120).default(5),
  gsmPort: z.string(),
  gsmBaud: z
    .number()
    .int()
    .refine((n) => GSM_BAUD_RATES.includes(n), { message: `Baud rate must be one of ${GSM_BAUD_RATES.join(", ")}` })
    .default(9600),
  staleSmsWindowMin: z.number().int().min(1).max(1440).default(30),
  ussdCode: z.string(),
});
export type BridgeSettings = z.infer<typeof BridgeSettingsSchema>;

export const SmsSettingsSchema = z.object({
  normalTemplate: smsTemplate,
  lateTemplate: smsTemplate,
  earlyLeaveTemplate: smsTemplate,
  smsEnabled: z.boolean(),
  earlyLeaveEnabled: z.boolean(),
  absentEnabled: z.boolean(),
  summaryEnabled: z.boolean(),
  summaryTime: timeString,
  absentTemplate: absentTemplate.default("Absent: {name} ({id}) was not present on {date}."),
  summaryTemplate: summaryTemplate.default(
    "Summary {date}: Present {present}, Absent {absent}, Late {late}, Total {total}",
  ),
  adminPhones: z.array(z.string().min(1)).max(2).default([]),
});
export type SmsSettings = z.infer<typeof SmsSettingsSchema>;

/** Days of the week the organisation is closed (0 = Sunday ... 6 = Saturday). */
export const DEFAULT_WEEKEND_DAYS: readonly number[] = [5, 6]; // Friday, Saturday (Bangladesh)

export const AppSettingsSchema = z.object({
  orgName: z.string(),
  timeZone: z.string().default("Asia/Dhaka"),
  notificationSound: z.boolean(),
  // Used by reports to tell school days from closures; the bridge does not read it.
  weekendDays: z
    .array(z.number().int().min(0).max(6))
    .refine((days) => new Set(days).size === days.length, { message: "Each weekend day may appear only once" })
    .default([...DEFAULT_WEEKEND_DAYS]),
});
export type AppSettings = z.infer<typeof AppSettingsSchema>;
