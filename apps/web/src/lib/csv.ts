export const PERSON_KINDS = ["staff", "teacher", "student"] as const;
export type PersonKind = (typeof PERSON_KINDS)[number];

/** Device user IDs: letters and digits only (no "/", so it is a valid Firestore doc id). */
export const PERSON_ID_PATTERN = /^[A-Za-z0-9]+$/;

export type PersonCsvRow = {
  /** 1-based CSV line number the record starts on (header = line 1). */
  line: number;
  id: string;
  name: string;
  kind: PersonKind;
  phone?: string;
  fatherPhone?: string;
  motherPhone?: string;
  className?: string;
  section?: string;
};

export type CsvRowError = { row: number; message: string };

type RawRecord = { line: number; fields: string[] };

/** RFC4180-ish tokenizer: quoted fields, embedded commas/quotes/newlines, CRLF/LF/CR. */
function tokenize(text: string): RawRecord[] {
  const records: RawRecord[] = [];
  let fields: string[] = [];
  let field = "";
  let inQuotes = false;
  let line = 1;
  let recordLine = 1;
  let touched = false;

  const endField = () => {
    fields.push(field);
    field = "";
  };
  const endRecord = () => {
    endField();
    records.push({ line: recordLine, fields });
    fields = [];
    touched = false;
  };

  for (let i = 0; i < text.length; i++) {
    const c = text[i] as string;
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        if (c === "\n") line++;
        field += c;
      }
      continue;
    }
    if (c === '"' && field === "") {
      inQuotes = true;
      touched = true;
    } else if (c === ",") {
      touched = true;
      endField();
    } else if (c === "\r" || c === "\n") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      if (touched || field !== "" || fields.length > 0) endRecord();
      line++;
      recordLine = line;
    } else {
      field += c;
      touched = true;
    }
  }
  if (touched || field !== "" || fields.length > 0) endRecord();
  return records;
}

const HEADER_ALIASES: Record<string, string> = {
  id: "id",
  name: "name",
  kind: "kind",
  role: "kind",
  phone: "phone",
  fatherphone: "fatherPhone",
  motherphone: "motherPhone",
  classname: "className",
  class: "className",
  section: "section",
};

function normalizeHeader(h: string): string | undefined {
  return HEADER_ALIASES[h.trim().toLowerCase().replace(/[\s_-]+/g, "")];
}

export function parsePeopleCsv(csv: string): { rows: PersonCsvRow[]; errors: CsvRowError[] } {
  const text = csv.charCodeAt(0) === 0xfeff ? csv.slice(1) : csv;
  const records = tokenize(text).filter((r) => !(r.fields.length === 1 && r.fields[0]?.trim() === ""));
  const rows: PersonCsvRow[] = [];
  const errors: CsvRowError[] = [];

  const header = records[0];
  if (!header) {
    return { rows, errors: [{ row: 1, message: "CSV is empty: a header row is required" }] };
  }
  const columns = header.fields.map(normalizeHeader);
  if (!columns.includes("id") || !columns.includes("name")) {
    return { rows, errors: [{ row: header.line, message: 'Header row must include "id" and "name" columns' }] };
  }

  const seen = new Set<string>();
  for (const rec of records.slice(1)) {
    const v: Record<string, string> = {};
    columns.forEach((col, idx) => {
      if (col && !(col in v)) v[col] = (rec.fields[idx] ?? "").trim();
    });
    const id = v.id ?? "";
    const name = v.name ?? "";
    const kindRaw = (v.kind ?? "").toLowerCase();
    const kind = kindRaw === "" ? "student" : kindRaw;

    if (id === "") {
      errors.push({ row: rec.line, message: "Missing id" });
      continue;
    }
    if (!PERSON_ID_PATTERN.test(id)) {
      errors.push({ row: rec.line, message: `Invalid id "${id}": use letters and digits only` });
      continue;
    }
    if (name === "") {
      errors.push({ row: rec.line, message: "Missing name" });
      continue;
    }
    if (!(PERSON_KINDS as readonly string[]).includes(kind)) {
      errors.push({ row: rec.line, message: `Invalid kind "${v.kind}": expected staff, teacher or student` });
      continue;
    }
    if (seen.has(id)) {
      errors.push({ row: rec.line, message: `Id "${id}" is a duplicate within the file` });
      continue;
    }
    seen.add(id);

    const row: PersonCsvRow = { line: rec.line, id, name, kind: kind as PersonKind };
    for (const key of ["phone", "fatherPhone", "motherPhone", "className", "section"] as const) {
      const val = v[key];
      if (val) row[key] = val;
    }
    rows.push(row);
  }
  return { rows, errors };
}
