import { describe, expect, it } from "vitest";
import { commandResultView } from "./command-view";

describe("commandResultView", () => {
  it("pending and running are in progress", () => {
    expect(commandResultView({ status: "pending" })).toMatchObject({
      label: "Waiting for the bridge",
      finished: false,
      isError: false,
    });
    expect(commandResultView({ status: "running" })).toMatchObject({ label: "Running", finished: false });
  });
  it("done with an object result is pretty JSON", () => {
    const v = commandResultView({ status: "done", result: { text: "ok" } });
    expect(v).toMatchObject({ label: "Done", finished: true, isError: false });
    expect(v.text).toBe(JSON.stringify({ text: "ok" }, null, 2));
  });
  it("done with a string result is shown as is; missing result is empty", () => {
    expect(commandResultView({ status: "done", result: "Balance 5" }).text).toBe("Balance 5");
    expect(commandResultView({ status: "done" }).text).toBe("");
  });
  it("error shows the error message", () => {
    const v = commandResultView({ status: "error", result: { error: "no modem" } });
    expect(v).toMatchObject({ label: "Failed", finished: true, isError: true, text: "no modem" });
    expect(commandResultView({ status: "error" }).text).toBe("Unknown error");
  });
  it("unknown status is treated as pending", () => {
    expect(commandResultView({ status: "weird" }).finished).toBe(false);
  });
});
