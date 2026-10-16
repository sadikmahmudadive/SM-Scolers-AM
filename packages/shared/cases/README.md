# Shared punch-rule cases

`punch-rules.json` is the language-neutral contract for the punch rules. Both the TypeScript
suite (Vitest, `packages/shared`) and the Python suite (bridge, Task 5) must pass every case.

- Keys are camelCase: `previousPunchMinutesAgo`, `isHoliday`, `graceMin`, `dismissal`.
- `time` is local `HH:mm:ss`; schedule `start`/`end`/`dismissal` are `HH:mm`.
- `dismissal` is absent (not `null`) when unset, so Python must read it with `.get("dismissal")`.
- `schedule` and `previousPunchMinutesAgo` may be `null`.
- Sections: `evaluate` (input -> flags), `direction` (status -> "in"/"out"), `punchId`.
