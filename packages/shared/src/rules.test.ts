import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { directionFromStatus, evaluatePunch, type PunchEvalInput, type PunchFlags } from "./rules";

type Cases = {
  evaluate: { name: string; input: PunchEvalInput; expected: PunchFlags }[];
  direction: { status: string; expected: "in" | "out" }[];
};

const cases = JSON.parse(
  readFileSync(new URL("../cases/punch-rules.json", import.meta.url), "utf8"),
) as Cases;

describe("evaluatePunch", () => {
  it.each(cases.evaluate)("$name", ({ input, expected }) => {
    expect(evaluatePunch(input)).toEqual(expected);
  });
});

describe("directionFromStatus", () => {
  it.each(cases.direction)("status '$status' -> $expected", ({ status, expected }) => {
    expect(directionFromStatus(status)).toBe(expected);
  });
});
