"use server";

import { revalidatePath } from "next/cache";
import type { Role } from "@hrm/shared";
import {
  assignManagerWith,
  changeRoleWith,
  createAccountWith,
  linkGuardianWith,
  resetPasswordWith,
  setAccountDisabledWith,
  unlinkGuardianWith,
  type AccountResult,
  type CreateAccountInput,
  type CreateAccountResult,
} from "@/lib/accounts";
import { adminAccountsDeps } from "@/lib/accounts-deps";
import { getSession } from "@/lib/session";

function done<T extends { ok: boolean }>(result: T, ...extra: string[]): T {
  if (result.ok) {
    revalidatePath("/accounts");
    for (const p of extra) revalidatePath(p);
  }
  return result;
}

export async function createAccount(input: CreateAccountInput): Promise<CreateAccountResult> {
  return done(await createAccountWith(adminAccountsDeps(), await getSession(), input));
}

export async function changeRole(uid: string, role: Role, personId?: string): Promise<AccountResult> {
  return done(await changeRoleWith(adminAccountsDeps(), await getSession(), uid, role, personId));
}

export async function setAccountDisabled(uid: string, disabled: boolean): Promise<AccountResult> {
  return done(await setAccountDisabledWith(adminAccountsDeps(), await getSession(), uid, disabled));
}

export async function resetPassword(uid: string, newPassword: string): Promise<AccountResult> {
  return done(await resetPasswordWith(adminAccountsDeps(), await getSession(), uid, newPassword));
}

export async function linkGuardian(personId: string, guardianUid: string): Promise<AccountResult> {
  return done(
    await linkGuardianWith(adminAccountsDeps(), await getSession(), personId, guardianUid),
    `/people/${personId}`,
  );
}

export async function unlinkGuardian(personId: string, guardianUid: string): Promise<AccountResult> {
  return done(
    await unlinkGuardianWith(adminAccountsDeps(), await getSession(), personId, guardianUid),
    `/people/${personId}`,
  );
}

export async function assignManager(personId: string, managerUid: string | null): Promise<AccountResult> {
  return done(
    await assignManagerWith(adminAccountsDeps(), await getSession(), personId, managerUid),
    `/people/${personId}`,
  );
}
