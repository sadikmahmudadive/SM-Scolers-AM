import type { AppSettings, BridgeSettings, SmsSettings } from "@hrm/shared";

// Shown (and used as form defaults) when a settings document does not exist yet.
// Templates mirror the bridge defaults in apps/bridge/src/bridge/models.py.
export const DEFAULT_BRIDGE: BridgeSettings = {
  pollIntervalSec: 10,
  zkTimeoutSec: 5,
  gsmPort: "",
  gsmBaud: 9600,
  staleSmsWindowMin: 30,
  ussdCode: "",
};

export const DEFAULT_SMS: SmsSettings = {
  normalTemplate: "Attendance: {name} ({id}) at {time}",
  lateTemplate: "LATE: {name} ({id}) punched at {time}. Expected in-time: {start} - {end}",
  earlyLeaveTemplate: "EARLY LEAVE: {name} ({id}) left at {time}. Expected dismissal: {end}",
  smsEnabled: true,
  earlyLeaveEnabled: false,
  absentEnabled: false,
  summaryEnabled: false,
  summaryTime: "16:00",
  absentTemplate: "Absent: {name} ({id}) was not present on {date}.",
  summaryTemplate: "Summary {date}: Present {present}, Absent {absent}, Late {late}, Total {total}",
  adminPhones: [],
};

export const DEFAULT_APP: AppSettings = {
  orgName: "My School",
  timeZone: "Asia/Dhaka",
  notificationSound: true,
};
