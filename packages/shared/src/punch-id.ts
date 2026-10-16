/** Deterministic attendance document id: `<personId>_<timestamp digits only>`. */
export function punchId(personId: string, timestamp: string): string {
  return `${personId}_${timestamp.replace(/\D/g, "")}`;
}
