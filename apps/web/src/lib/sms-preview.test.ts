import { describe, expect, it } from "vitest";
import { previewTemplate } from "./sms-preview";

describe("previewTemplate", () => {
  it("fills punch placeholders with sample values", () => {
    const r = previewTemplate("normalTemplate", "{name} ({id}) {status} {time} {date} {role} {start}-{end}");
    expect(r).toEqual({ text: "Ayesha Rahman (12) Check-In 08:21 AM 16-Oct-2026 student 07:45-08:15", unknown: [], syntaxError: null });
  });
  it("uses the absent and summary sets", () => {
    expect(previewTemplate("absentTemplate", "{name} {id} {date}").text).toBe("Ayesha Rahman 12 16-Oct-2026");
    expect(previewTemplate("summaryTemplate", "{present}/{total}").unknown).toEqual([]);
  });
  it("lists unknown placeholders and leaves them in place", () => {
    const r = previewTemplate("normalTemplate", "Hi {bogus} {name} {present}");
    expect(r.unknown).toEqual(["{bogus}", "{present}"]);
    expect(r.text).toBe("Hi {bogus} Ayesha Rahman {present}");
  });
  it("reports a template Python's str.format would reject, and renders doubled braces literally", () => {
    expect(previewTemplate("normalTemplate", "Dear {name, your child").syntaxError).toMatch(/Unclosed/);
    expect(previewTemplate("absentTemplate", "Bye :-} {name}").syntaxError).toMatch(/Single/);
    expect(previewTemplate("summaryTemplate", "{} {present}").syntaxError).toMatch(/Empty/);
    const ok = previewTemplate("normalTemplate", "{{ok}} {name}");
    expect(ok.syntaxError).toBeNull();
    expect(ok.text).toBe("{ok} Ayesha Rahman");
  });
});
