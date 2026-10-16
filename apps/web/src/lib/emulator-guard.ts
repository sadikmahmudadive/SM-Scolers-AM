/** Throws when an emulator env var is set in production (it would disable token signature checks). */
export function assertNoEmulatorInProduction(
  env: Record<string, string | undefined>,
  names: readonly string[],
): void {
  if (env.NODE_ENV !== "production") return;
  const bad = names.find((n) => env[n]);
  if (bad) throw new Error(`Refusing to run in production with emulator variable ${bad} set`);
}
