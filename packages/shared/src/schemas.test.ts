import { describe, expect, it } from "vitest";
import {
  ABSENT_PLACEHOLDERS,
  AppSettingsSchema,
  AttendanceSchema,
  BridgeSettingsSchema,
  COLLECTIONS,
  COMMAND_TYPES,
  CommandSchema,
  DeviceSchema,
  HolidaySchema,
  PersonSchema,
  SMS_PLACEHOLDERS,
  ScheduleSchema,
  SUMMARY_PLACEHOLDERS,
  SmsLogSchema,
  SmsSettingsSchema,
  can,
  findUnknownPlaceholders,
} from "./index";

const validStudent = {
  name: "Rahim Uddin",
  kind: "student",
  className: "Six",
  section: "A",
  fatherPhone: "01711111111",
  deviceEnrolled: true,
  active: true,
  createdAt: new Date("2026-01-01T00:00:00Z"),
};

describe("PersonSchema", () => {
  it("accepts a valid student and defaults guardianUids", () => {
    const parsed = PersonSchema.parse(validStudent);
    expect(parsed.kind).toBe("student");
    expect(parsed.guardianUids).toEqual([]);
  });

  it("rejects an unknown kind", () => {
    expect(PersonSchema.safeParse({ ...validStudent, kind: "alien" }).success).toBe(false);
  });
});

describe("AttendanceSchema", () => {
  const base = {
    personId: "42",
    ts: new Date("2026-03-01T03:00:00Z"),
    date: "2026-03-01",
    status: "0",
    direction: "in",
    deviceId: "dev1",
    late: false,
    earlyLeave: false,
  };
  it("accepts a valid punch", () => {
    expect(AttendanceSchema.safeParse(base).success).toBe(true);
  });
  it("rejects a malformed date and bad direction", () => {
    expect(AttendanceSchema.safeParse({ ...base, date: "01-03-2026" }).success).toBe(false);
    expect(AttendanceSchema.safeParse({ ...base, direction: "sideways" }).success).toBe(false);
  });
});

describe("ScheduleSchema", () => {
  const base = { name: "Day", start: "08:00", end: "09:00", graceMin: 5, appliesTo: ["Six"] };
  it("accepts a valid schedule with optional dismissal", () => {
    expect(ScheduleSchema.safeParse(base).success).toBe(true);
    expect(ScheduleSchema.safeParse({ ...base, dismissal: "15:30" }).success).toBe(true);
  });
  it("rejects start: 8am", () => {
    expect(ScheduleSchema.safeParse({ ...base, start: "8am" }).success).toBe(false);
  });
  it("rejects out-of-range times", () => {
    expect(ScheduleSchema.safeParse({ ...base, end: "25:00" }).success).toBe(false);
    expect(ScheduleSchema.safeParse({ ...base, dismissal: "12:60" }).success).toBe(false);
  });
});

describe("HolidaySchema", () => {
  it("requires a name", () => {
    expect(HolidaySchema.safeParse({ name: "Eid" }).success).toBe(true);
    expect(HolidaySchema.safeParse({}).success).toBe(false);
  });
});

describe("SmsLogSchema", () => {
  const base = {
    personId: "42",
    phone: "01711111111",
    body: "hi",
    kind: "late",
    status: "sent",
    ts: new Date(),
  };
  it("accepts valid and rejects unknown kind/status", () => {
    expect(SmsLogSchema.safeParse(base).success).toBe(true);
    expect(SmsLogSchema.safeParse({ ...base, kind: "x" }).success).toBe(false);
    expect(SmsLogSchema.safeParse({ ...base, status: "x" }).success).toBe(false);
    expect(SmsLogSchema.safeParse({ ...base, status: "skipped-stale" }).success).toBe(true);
  });
  it("accepts an optional org-local date string and rejects a malformed one", () => {
    expect(SmsLogSchema.safeParse({ ...base, date: "2026-10-16" }).success).toBe(true);
    expect(SmsLogSchema.safeParse({ ...base, date: "16/10/2026" }).success).toBe(false);
  });
});

describe("DeviceSchema", () => {
  it("accepts a device", () => {
    expect(
      DeviceSchema.safeParse({ name: "Gate", ip: "192.168.1.10", port: 4370, lastSeen: new Date() })
        .success,
    ).toBe(true);
  });
});

describe("CommandSchema", () => {
  const base = { payload: {}, status: "pending" };
  it("accepts exactly the five command types", () => {
    for (const type of ["test_sms", "ussd", "sync_device_users", "read_inbox", "at_command"]) {
      expect(CommandSchema.safeParse({ ...base, type }).success).toBe(true);
    }
    expect([...COMMAND_TYPES]).toEqual([
      "test_sms",
      "ussd",
      "sync_device_users",
      "read_inbox",
      "at_command",
    ]);
  });
  it("rejects other types", () => {
    expect(CommandSchema.safeParse({ ...base, type: "format_disk" }).success).toBe(false);
  });
});

describe("settings schemas", () => {
  it("BridgeSettingsSchema applies defaults", () => {
    const parsed = BridgeSettingsSchema.parse({ gsmPort: "COM3", ussdCode: "*222#" });
    expect(parsed.pollIntervalSec).toBe(10);
    expect(parsed.zkTimeoutSec).toBe(5);
    expect(parsed.gsmBaud).toBe(9600);
    expect(parsed.staleSmsWindowMin).toBe(30);
  });
  it("BridgeSettingsSchema enforces upper bounds and allowed baud rates", () => {
    const base = { gsmPort: "COM3", ussdCode: "*222#" };
    expect(BridgeSettingsSchema.safeParse({ ...base, pollIntervalSec: 3601 }).success).toBe(false);
    expect(BridgeSettingsSchema.safeParse({ ...base, pollIntervalSec: 3600 }).success).toBe(true);
    expect(BridgeSettingsSchema.safeParse({ ...base, zkTimeoutSec: 121 }).success).toBe(false);
    expect(BridgeSettingsSchema.safeParse({ ...base, staleSmsWindowMin: 1441 }).success).toBe(false);
    expect(BridgeSettingsSchema.safeParse({ ...base, gsmBaud: 1234 }).success).toBe(false);
    expect(BridgeSettingsSchema.safeParse({ ...base, gsmBaud: 115200 }).success).toBe(true);
  });

  it("BridgeSettingsSchema rejects pollIntervalSec < 1", () => {
    expect(
      BridgeSettingsSchema.safeParse({ gsmPort: "COM3", ussdCode: "*222#", pollIntervalSec: 0 })
        .success,
    ).toBe(false);
  });
  it("AppSettingsSchema defaults time zone to Asia/Dhaka", () => {
    const parsed = AppSettingsSchema.parse({ orgName: "School", notificationSound: true });
    expect(parsed.timeZone).toBe("Asia/Dhaka");
  });

  const sms = {
    normalTemplate: "{name} arrived at {time}",
    lateTemplate: "{name} is late: {time} (start {start})",
    earlyLeaveTemplate: "{name} left early at {time}",
    smsEnabled: true,
    earlyLeaveEnabled: true,
    absentEnabled: false,
    summaryEnabled: true,
    summaryTime: "18:00",
  };
  it("SmsSettingsSchema accepts known placeholders", () => {
    expect(SmsSettingsSchema.safeParse(sms).success).toBe(true);
  });
  it("SmsSettingsSchema rejects unknown placeholders", () => {
    expect(SmsSettingsSchema.safeParse({ ...sms, normalTemplate: "Hi {bogus}" }).success).toBe(
      false,
    );
    expect(SmsSettingsSchema.safeParse({ ...sms, summaryTime: "6pm" }).success).toBe(false);
  });
  it("SmsSettingsSchema defaults the absent/summary templates and adminPhones", () => {
    const parsed = SmsSettingsSchema.parse(sms);
    expect(parsed.absentTemplate).toBe("Absent: {name} ({id}) was not present on {date}.");
    expect(parsed.summaryTemplate).toBe(
      "Summary {date}: Present {present}, Absent {absent}, Late {late}, Total {total}",
    );
    expect(parsed.adminPhones).toEqual([]);
  });
  it("validates absent/summary templates against their own placeholder sets", () => {
    expect([...ABSENT_PLACEHOLDERS]).toEqual(["{name}", "{id}", "{date}"]);
    expect([...SUMMARY_PLACEHOLDERS]).toEqual([
      "{date}",
      "{present}",
      "{absent}",
      "{late}",
      "{total}",
    ]);
    // {time} is a punch placeholder, not an absent one; {present} is not a punch one.
    expect(SmsSettingsSchema.safeParse({ ...sms, absentTemplate: "{name} at {time}" }).success).toBe(
      false,
    );
    expect(
      SmsSettingsSchema.safeParse({ ...sms, normalTemplate: "{present} here" }).success,
    ).toBe(false);
    expect(
      SmsSettingsSchema.safeParse({ ...sms, summaryTemplate: "{name}: {present}" }).success,
    ).toBe(false);
    expect(
      SmsSettingsSchema.safeParse({
        ...sms,
        absentTemplate: "{name} {id} {date}",
        summaryTemplate: "{date} {present} {absent} {late} {total}",
      }).success,
    ).toBe(true);
  });
  it("adminPhones holds at most two non-empty phones", () => {
    expect(SmsSettingsSchema.safeParse({ ...sms, adminPhones: ["017", "018"] }).success).toBe(true);
    expect(SmsSettingsSchema.safeParse({ ...sms, adminPhones: ["017", "018", "019"] }).success).toBe(
      false,
    );
    expect(SmsSettingsSchema.safeParse({ ...sms, adminPhones: [""] }).success).toBe(false);
  });
  it("findUnknownPlaceholders lists unknown tokens", () => {
    expect(SMS_PLACEHOLDERS).toEqual([
      "{id}",
      "{name}",
      "{time}",
      "{date}",
      "{status}",
      "{role}",
      "{start}",
      "{end}",
    ]);
    expect(findUnknownPlaceholders("{name} {bogus} {x}")).toEqual(["{bogus}", "{x}"]);
    expect(findUnknownPlaceholders("{name} at {time}")).toEqual([]);
  });
});

describe("can()", () => {
  it("guardian cannot manage; admin can", () => {
    expect(can("guardian", "manage")).toBe(false);
    expect(can("admin", "manage")).toBe(true);
  });
  it("matches the role matrix", () => {
    expect(can("admin", "read:all")).toBe(true);
    expect(can("admin", "read:children")).toBe(true);
    expect(can("manager", "read:team")).toBe(true);
    expect(can("manager", "read:self")).toBe(true);
    expect(can("manager", "read:all")).toBe(false);
    expect(can("manager", "manage")).toBe(false);
    expect(can("staff", "read:self")).toBe(true);
    expect(can("staff", "read:team")).toBe(false);
    expect(can("guardian", "read:children")).toBe(true);
    expect(can("guardian", "read:self")).toBe(false);
  });
});

describe("COLLECTIONS", () => {
  it("maps keys to the Firestore collection names", () => {
    expect(COLLECTIONS).toEqual({
      people: "people",
      attendance: "attendance",
      schedules: "schedules",
      holidays: "holidays",
      smsLog: "smsLog",
      devices: "devices",
      commands: "commands",
      settings: "settings",
      bridgeStatus: "bridgeStatus",
      users: "users",
    });
  });
});
