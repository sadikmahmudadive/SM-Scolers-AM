// Pure argument parsing for create-first-admin.mjs (unit tested in create-admin-args.test.mjs).
import { parseArgs } from "node:util";

export const MIN_PASSWORD_LENGTH = 10;

export class UsageError extends Error {}

export const USAGE =
  "Usage: create-admin --email <email> [--name <display name>] [--reset-password] [--yes] [--project <id>]\n" +
  `  Password comes from env ADMIN_PASSWORD or a hidden prompt (min ${MIN_PASSWORD_LENGTH} characters).\n` +
  "  Credentials: FIREBASE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS, or both emulator hosts.";

/**
 * Parses the script's argv (without node and the script path).
 * `pnpm --filter @hrm/web create-admin -- --email ...` forwards the literal `--`, so ONE leading
 * `--` is stripped; everything else is parsed strictly (unknown flags and positionals are errors).
 * Returns {help: true} for --help; otherwise validated {email, name, project, resetPassword, yes}.
 * Throws UsageError on bad input.
 */
export function parseCliArgs(argv) {
  const args = argv[0] === "--" ? argv.slice(1) : argv;
  let values;
  try {
    ({ values } = parseArgs({
      args,
      options: {
        email: { type: "string" },
        name: { type: "string" },
        project: { type: "string" },
        "reset-password": { type: "boolean", default: false },
        yes: { type: "boolean", default: false },
        help: { type: "boolean", default: false },
      },
      strict: true,
      allowPositionals: false,
    }));
  } catch (e) {
    throw new UsageError(`${e.message}\n${USAGE}`);
  }
  if (values.help) return { help: true };
  const email = (values.email ?? "").trim().toLowerCase();
  if (!email) throw new UsageError(`--email is required\n${USAGE}`);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new UsageError("--email is not a valid email address");
  const name = values.name?.trim();
  if (values.name !== undefined && !name) throw new UsageError("--name must not be empty");
  return {
    help: false,
    email,
    name: name || undefined,
    project: values.project?.trim() || undefined,
    resetPassword: values["reset-password"],
    yes: values.yes,
  };
}
