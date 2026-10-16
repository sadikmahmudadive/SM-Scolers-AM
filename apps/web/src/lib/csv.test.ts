import { describe, expect, it } from "vitest";
import { parsePeopleCsv } from "./csv";

describe("parsePeopleCsv", () => {
  it("returns a row error for missing name but still returns valid rows", () => {
    const r = parsePeopleCsv("id,name,kind\n1,Ann,student\n2,,student\n3,Cy,teacher\n");
    expect(r.rows.map((x) => x.id)).toEqual(["1", "3"]);
    expect(r.errors).toEqual([{ row: 3, message: expect.stringContaining("name") }]);
  });
  it("reports missing id", () => {
    const r = parsePeopleCsv("id,name\n,Ann\n");
    expect(r.rows).toEqual([]);
    expect(r.errors[0]).toEqual({ row: 2, message: expect.stringContaining("id") });
  });
  it("reports the second occurrence of a duplicate id and keeps the first", () => {
    const r = parsePeopleCsv("id,name\n1,Ann\n2,Bob\n1,Again\n");
    expect(r.rows.map((x) => x.name)).toEqual(["Ann", "Bob"]);
    expect(r.errors).toEqual([{ row: 4, message: expect.stringContaining("duplicate") }]);
  });
  it("handles quoted fields with commas, embedded quotes and newlines", () => {
    const r = parsePeopleCsv('id,name,section\n1,"Smith, ""Jo"" A",\n2,"Line1\nLine2",B\n3,Zed,C\n');
    expect(r.rows[0]?.name).toBe('Smith, "Jo" A');
    expect(r.rows[1]?.name).toBe("Line1\nLine2");
    expect(r.rows[1]?.section).toBe("B");
    // row 3 starts on physical line 5 because the quoted field spans two lines
    expect(r.rows[2]?.line).toBe(5);
  });
  it("handles CRLF and a BOM", () => {
    const r = parsePeopleCsv("\uFEFFid,name\r\n1,Ann\r\n2,Bob\r\n");
    expect(r.errors).toEqual([]);
    expect(r.rows.map((x) => x.id)).toEqual(["1", "2"]);
  });
  it("accepts alias headers case-insensitively", () => {
    const r = parsePeopleCsv("ID,Name,Role,father_phone,mother_phone,class_name,Section\n7,Ann,teacher,111,222,Ten,A\n");
    expect(r.rows[0]).toMatchObject({
      id: "7",
      kind: "teacher",
      fatherPhone: "111",
      motherPhone: "222",
      className: "Ten",
      section: "A",
    });
  });
  it("defaults blank kind to student", () => {
    const r = parsePeopleCsv("id,name,kind\n1,Ann,\n2,Bob\n");
    expect(r.rows.map((x) => x.kind)).toEqual(["student", "student"]);
  });
  it("reports an invalid kind", () => {
    const r = parsePeopleCsv("id,name,kind\n1,Ann,alien\n");
    expect(r.rows).toEqual([]);
    expect(r.errors).toEqual([{ row: 2, message: expect.stringContaining("kind") }]);
  });
  it("reports an invalid id", () => {
    const r = parsePeopleCsv("id,name\na/b,Ann\n");
    expect(r.errors[0]?.row).toBe(2);
  });
  it("uses 1-based CSV line numbers and skips blank lines", () => {
    const r = parsePeopleCsv("id,name\n1,A\n\n2,\n");
    expect(r.errors).toEqual([{ row: 4, message: expect.stringContaining("name") }]);
  });
  it("requires id and name headers", () => {
    const r = parsePeopleCsv("foo,bar\n1,2\n");
    expect(r.rows).toEqual([]);
    expect(r.errors[0]?.row).toBe(1);
  });
  it("handles empty input", () => {
    const r = parsePeopleCsv("");
    expect(r.rows).toEqual([]);
    expect(r.errors[0]?.row).toBe(1);
  });
});
