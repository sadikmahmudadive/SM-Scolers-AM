import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { punchId } from "./punch-id";

type Cases = { punchId: { personId: string; timestamp: string; expected: string }[] };

const cases = JSON.parse(
  readFileSync(new URL("../cases/punch-rules.json", import.meta.url), "utf8"),
) as Cases;

describe("punchId", () => {
  it.each(cases.punchId)("$personId @ $timestamp -> $expected", ({ personId, timestamp, expected }) => {
    expect(punchId(personId, timestamp)).toBe(expected);
  });
});
