import { CommandSchema, type Command, type CommandType } from "@hrm/shared";
import type { Session } from "./access";

export function buildCommandDoc(
  type: CommandType,
  payload: Record<string, unknown>,
  createdBy: string,
  now: Date,
): Command {
  return CommandSchema.parse({ type, payload, status: "pending", createdBy, createdAt: now });
}

export type CommandDeps = {
  /** Writes commands/{auto-id} and returns the generated id. */
  add: (doc: Command) => Promise<string>;
  now: () => Date;
};

export async function enqueueCommandWith(
  deps: CommandDeps,
  caller: Session | null,
  type: CommandType,
  payload: Record<string, unknown>,
): Promise<string> {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
  return deps.add(buildCommandDoc(type, payload, caller.uid, deps.now()));
}
