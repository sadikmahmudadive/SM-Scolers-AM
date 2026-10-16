import { PersonSchema } from "@hrm/shared";
import { z } from "zod";
import type { Session } from "./access";
import { parsePeopleCsv, PERSON_ID_PATTERN, type CsvRowError, type PersonCsvRow } from "./csv";

export const MAX_CSV_BYTES = 1024 * 1024;
const DEFAULT_BATCH_SIZE = 400;

export type PeopleDeps = {
  now: () => Date;
  /** Firestore FieldValue.delete() sentinel, injected so this module stays pure. */
  deleteMarker: unknown;
  batchSize?: number;
  /** Create-only write; must throw an error with code 6 (ALREADY_EXISTS) when the doc exists. */
  create: (id: string, data: Record<string, unknown>) => Promise<void>;
  /** Partial update; must throw an error with code 5 (NOT_FOUND) when the doc is missing. */
  update: (id: string, patch: Record<string, unknown>) => Promise<void>;
  /** Deletes the people doc only. Attendance history is deliberately out of reach of this interface. */
  remove: (id: string) => Promise<void>;
  existingIds: (ids: string[]) => Promise<Set<string>>;
  /** Create-only batched write of up to batchSize docs in one commit. */
  createMany: (items: { id: string; data: Record<string, unknown> }[]) => Promise<void>;
};

export type Result = { ok: true } | { ok: false; error: string };

const editable = PersonSchema.pick({
  name: true,
  kind: true,
  phone: true,
  fatherPhone: true,
  motherPhone: true,
  className: true,
  section: true,
  departmentId: true,
  active: true,
});

const createSchema = editable.partial({ active: true }).extend({
  id: z.string().regex(PERSON_ID_PATTERN, "ID must be letters and digits only (no spaces or /)"),
  name: z.string().trim().min(1, "Name is required"),
});
export type CreatePersonInput = z.input<typeof createSchema>;

const updateSchema = editable.partial().extend({ name: z.string().trim().min(1, "Name is required").optional() });
export type UpdatePersonPatch = z.input<typeof updateSchema>;

const OPTIONAL_STRINGS = [
  "phone",
  "fatherPhone",
  "motherPhone",
  "className",
  "section",
  "departmentId",
] as const;

function assertAdmin(caller: Session | null): void {
  if (!caller || caller.role !== "admin") throw new Error("Forbidden: admin only");
}

function errorCode(e: unknown): unknown {
  return typeof e === "object" && e !== null ? (e as { code?: unknown }).code : undefined;
}

function firstIssue(e: z.ZodError): string {
  const i = e.issues[0];
  if (!i) return "Invalid input";
  const path = i.path.join(".");
  return path ? `${path}: ${i.message}` : i.message;
}

export async function createPersonWith(deps: PeopleDeps, caller: Session | null, input: CreatePersonInput): Promise<Result> {
  assertAdmin(caller);
  const parsed = createSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  const { id, ...rest } = parsed.data;
  const data: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(rest)) {
    if (v === undefined || v === "") continue;
    data[k] = v;
  }
  data.guardianUids = [];
  data.deviceEnrolled = false;
  data.active = rest.active ?? true;
  data.createdAt = deps.now();
  try {
    await deps.create(id, data);
  } catch (e) {
    if (errorCode(e) === 6) return { ok: false, error: `A person with ID "${id}" already exists` };
    throw e;
  }
  return { ok: true };
}

export async function updatePersonWith(
  deps: PeopleDeps,
  caller: Session | null,
  id: string,
  patch: UpdatePersonPatch,
): Promise<Result> {
  assertAdmin(caller);
  if (!PERSON_ID_PATTERN.test(id)) return { ok: false, error: "Invalid person ID" };
  // Unknown keys (id, createdAt, guardianUids, ...) are stripped by the schema: they cannot be changed here.
  const parsed = updateSchema.safeParse(patch);
  if (!parsed.success) return { ok: false, error: firstIssue(parsed.error) };
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(parsed.data)) {
    if (v === undefined) continue;
    if (v === "" && (OPTIONAL_STRINGS as readonly string[]).includes(k)) out[k] = deps.deleteMarker;
    else out[k] = v;
  }
  if (Object.keys(out).length === 0) return { ok: true };
  try {
    await deps.update(id, out);
  } catch (e) {
    if (errorCode(e) === 5) return { ok: false, error: "Person not found" };
    throw e;
  }
  return { ok: true };
}

export async function deletePersonWith(deps: PeopleDeps, caller: Session | null, id: string): Promise<Result> {
  assertAdmin(caller);
  if (!PERSON_ID_PATTERN.test(id)) return { ok: false, error: "Invalid person ID" };
  await deps.remove(id);
  return { ok: true };
}

function omitLine(r: PersonCsvRow): Omit<PersonCsvRow, "line" | "id"> {
  const { line, id, ...rest } = r;
  void line;
  void id;
  return rest;
}

export type ImportResult = { imported: number; errors: CsvRowError[] };

export async function importPeopleCsvWith(deps: PeopleDeps, caller: Session | null, csv: string): Promise<ImportResult> {
  assertAdmin(caller);
  if (Buffer.byteLength(csv, "utf8") > MAX_CSV_BYTES) {
    return { imported: 0, errors: [{ row: 1, message: "File too large (max 1 MB)" }] };
  }
  const { rows, errors } = parsePeopleCsv(csv);
  const all: CsvRowError[] = [...errors];
  const existing = rows.length > 0 ? await deps.existingIds(rows.map((r) => r.id)) : new Set<string>();
  const fresh = rows.filter((r) => {
    if (existing.has(r.id)) {
      all.push({ row: r.line, message: `A person with ID "${r.id}" already exists` });
      return false;
    }
    return true;
  });

  const now = deps.now();
  const size = deps.batchSize ?? DEFAULT_BATCH_SIZE;
  let imported = 0;
  for (let i = 0; i < fresh.length; i += size) {
    const chunk = fresh.slice(i, i + size);
    const items = chunk.map((r) => ({
      id: r.id,
      data: { ...omitLine(r), guardianUids: [], deviceEnrolled: false, active: true, createdAt: now } as Record<string, unknown>,
    }));
    try {
      await deps.createMany(items);
      imported += items.length;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "write failed";
      for (const r of chunk) all.push({ row: r.line, message: `Not imported: ${msg}` });
    }
  }
  all.sort((a, b) => a.row - b.row);
  return { imported, errors: all };
}
