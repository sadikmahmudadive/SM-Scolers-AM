"use server";

import { revalidatePath } from "next/cache";
import { adminPeopleDeps } from "@/lib/people-deps";
import {
  createPersonWith,
  deletePersonWith,
  importPeopleCsvWith,
  updatePersonWith,
  type CreatePersonInput,
  type ImportResult,
  type Result,
  type UpdatePersonPatch,
} from "@/lib/people";
import { getSession } from "@/lib/session";
import { enqueueCommand } from "./commands";

export async function createPerson(input: CreatePersonInput): Promise<Result> {
  const result = await createPersonWith(adminPeopleDeps(), await getSession(), input);
  if (result.ok) revalidatePath("/people");
  return result;
}

export async function updatePerson(id: string, patch: UpdatePersonPatch): Promise<Result> {
  const result = await updatePersonWith(adminPeopleDeps(), await getSession(), id, patch);
  if (result.ok) {
    revalidatePath("/people");
    revalidatePath(`/people/${id}`);
  }
  return result;
}

export async function deletePerson(id: string): Promise<Result> {
  const result = await deletePersonWith(adminPeopleDeps(), await getSession(), id);
  if (result.ok) revalidatePath("/people");
  return result;
}

export async function importPeopleCsv(csv: string): Promise<ImportResult> {
  const result = await importPeopleCsvWith(adminPeopleDeps(), await getSession(), csv);
  if (result.imported > 0) revalidatePath("/people");
  return result;
}

export async function syncDeviceUsers(): Promise<void> {
  await enqueueCommand("sync_device_users", {});
  revalidatePath("/people");
}
