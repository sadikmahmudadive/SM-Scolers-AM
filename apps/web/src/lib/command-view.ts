export type CommandView = { label: string; finished: boolean; isError: boolean; text: string };

type CommandLike = { status?: string; result?: unknown };

function asText(result: unknown): string {
  if (result === undefined || result === null) return "";
  return typeof result === "string" ? result : JSON.stringify(result, null, 2);
}

/** Maps a commands/{id} doc to what the GSM console shows. */
export function commandResultView(doc: CommandLike): CommandView {
  switch (doc.status) {
    case "running":
      return { label: "Running", finished: false, isError: false, text: "" };
    case "done":
      return { label: "Done", finished: true, isError: false, text: asText(doc.result) };
    case "error": {
      const r = doc.result;
      const msg =
        typeof r === "object" && r !== null && typeof (r as { error?: unknown }).error === "string"
          ? (r as { error: string }).error
          : asText(r);
      return { label: "Failed", finished: true, isError: true, text: msg || "Unknown error" };
    }
    default:
      return { label: "Waiting for the bridge", finished: false, isError: false, text: "" };
  }
}
