"use server";

import { revalidatePath } from "next/cache";
import type { AppSettings, BridgeSettings, SmsSettings } from "@hrm/shared";
import { adminSettingsDeps } from "@/lib/settings-deps";
import {
  addHolidayWith,
  deleteDeviceWith,
  deleteScheduleWith,
  exportBackupWith,
  removeHolidayWith,
  restoreBackupWith,
  saveAppSettingsWith,
  saveBridgeSettingsWith,
  saveDeviceWith,
  saveScheduleWith,
  saveSmsSettingsWith,
  type DeviceInput,
  type Result,
  type RestoreResult,
  type ScheduleInput,
} from "@/lib/settings";
import { getSession } from "@/lib/session";

async function done(result: Result): Promise<Result> {
  if (result.ok) revalidatePath("/settings");
  return result;
}

export async function saveSchedule(input: ScheduleInput): Promise<Result> {
  return done(await saveScheduleWith(adminSettingsDeps(), await getSession(), input));
}

export async function deleteSchedule(id: string): Promise<Result> {
  return done(await deleteScheduleWith(adminSettingsDeps(), await getSession(), id));
}

export async function addHoliday(date: string, name: string): Promise<Result> {
  return done(await addHolidayWith(adminSettingsDeps(), await getSession(), date, name));
}

export async function removeHoliday(date: string): Promise<Result> {
  return done(await removeHolidayWith(adminSettingsDeps(), await getSession(), date));
}

export async function saveSmsSettings(s: SmsSettings): Promise<Result> {
  return done(await saveSmsSettingsWith(adminSettingsDeps(), await getSession(), s));
}

export async function saveBridgeSettings(s: BridgeSettings): Promise<Result> {
  return done(await saveBridgeSettingsWith(adminSettingsDeps(), await getSession(), s));
}

export async function saveAppSettings(s: AppSettings): Promise<Result> {
  return done(await saveAppSettingsWith(adminSettingsDeps(), await getSession(), s));
}

export async function saveDevice(d: DeviceInput): Promise<Result> {
  return done(await saveDeviceWith(adminSettingsDeps(), await getSession(), d));
}

export async function deleteDevice(id: string): Promise<Result> {
  return done(await deleteDeviceWith(adminSettingsDeps(), await getSession(), id));
}

export async function exportBackup(): Promise<string> {
  return exportBackupWith(adminSettingsDeps(), await getSession());
}

export async function restoreBackup(json: string): Promise<RestoreResult> {
  const result = await restoreBackupWith(adminSettingsDeps(), await getSession(), json);
  if (result.ok) {
    revalidatePath("/settings");
    revalidatePath("/people");
  }
  return result;
}
