import { describe, expect, it } from "vitest";
import { csvCell, toCsv } from "./csv-export";

describe("csvCell", () => {
  it("leaves plain text alone", () => expect(csvCell("abc")).toBe("abc"));
  it("quotes commas, quotes and newlines", () => {
    expect(csvCell("a,b")).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell("a\nb")).toBe('"a\nb"');
  });
  it("defuses formula prefixes", () => {
    expect(csvCell("=1+1")).toBe("'=1+1");
    expect(csvCell("+1")).toBe("'+1");
    expect(csvCell("-1")).toBe("'-1");
    expect(csvCell("@x")).toBe("'@x");
    expect(csvCell("\tx")).toBe("'\tx");
    expect(csvCell("\rx")).toBe('"\'\rx"');
    expect(csvCell('=HYPERLINK("u","v")')).toBe('"\'=HYPERLINK(""u"",""v"")"');
  });
  it("renders booleans, numbers and undefined", () => {
    expect(csvCell(true)).toBe("true");
    expect(csvCell(5)).toBe("5");
    expect(csvCell(undefined)).toBe("");
  });
});

describe("toCsv", () => {
  it("joins header and rows with CRLF", () => {
    expect(toCsv(["a", "b"], [["1", "x,y"]])).toBe('a,b\r\n1,"x,y"\r\n');
  });
});
