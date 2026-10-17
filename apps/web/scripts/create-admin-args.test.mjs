import { describe, expect, it } from "vitest";
import { UsageError, parseCliArgs } from "./create-admin-args.mjs";

describe("parseCliArgs", () => {
  it("parses flags given directly", () => {
    const r = parseCliArgs(["--email", "A@B.test", "--project", "demo-hrm"]);
    expect(r.help).toBe(false);
    expect(r.email).toBe("a@b.test");
    expect(r.project).toBe("demo-hrm");
    expect(r.resetPassword).toBe(false);
    expect(r.yes).toBe(false);
  });

  it("strips the single leading -- that pnpm passes through", () => {
    const r = parseCliArgs(["--", "--email", "a@b.test", "--project", "demo-hrm", "--yes", "--reset-password", "--name", " Head "]);
    expect(r.email).toBe("a@b.test");
    expect(r.project).toBe("demo-hrm");
    expect(r.yes).toBe(true);
    expect(r.resetPassword).toBe(true);
    expect(r.name).toBe("Head");
  });

  it("returns help without requiring --email (with or without a leading --)", () => {
    expect(parseCliArgs(["--", "--help"]).help).toBe(true);
    expect(parseCliArgs(["--help"]).help).toBe(true);
    expect(parseCliArgs(["--", "--email", "a@b.test", "--project", "demo-hrm", "--help"]).help).toBe(true);
  });

  it("reports a missing --email as a usage error", () => {
    expect(() => parseCliArgs(["--", "--project", "demo-hrm"])).toThrow(UsageError);
    expect(() => parseCliArgs([])).toThrow(/--email is required/);
  });

  it("reports an unknown flag as a usage error", () => {
    expect(() => parseCliArgs(["--", "--email", "a@b.test", "--bogus"])).toThrow(UsageError);
  });

  it("strips only ONE leading --; a second one is a stray positional", () => {
    expect(() => parseCliArgs(["--", "--", "--email", "a@b.test"])).toThrow(UsageError);
  });

  it("rejects an invalid email and an empty name", () => {
    expect(() => parseCliArgs(["--email", "nope"])).toThrow(/not a valid email/);
    expect(() => parseCliArgs(["--email", "a@b.test", "--name", "  "])).toThrow(/--name must not be empty/);
  });
});
