"use server";

import { COLLECTIONS, type CommandType } from "@hrm/shared";
import { enqueueCommandWith } from "@/lib/commands";
import { getAdminDb } from "@/lib/firebase-admin";
import { getSession } from "@/lib/session";

export async function enqueueCommand(type: CommandType, payload: Record<string, unknown> = {}): Promise<string> {
  const caller = await getSession();
  return enqueueCommandWith(
    {
      now: () => new Date(),
      add: async (doc) => (await getAdminDb().collection(COLLECTIONS.commands).add(doc)).id,
    },
    caller,
    type,
    payload,
  );
}
