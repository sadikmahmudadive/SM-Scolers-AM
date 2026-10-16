"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { doc, onSnapshot } from "firebase/firestore";
import type { CommandType } from "@hrm/shared";
import { enqueueCommand } from "@/actions/commands";
import { syncDeviceUsers } from "@/actions/people";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { commandResultView, type CommandView } from "@/lib/command-view";
import { acquireLiveAuth, getClientDb, releaseLiveAuth } from "@/lib/firebase-live";
import { Field, FormMessage } from "./shared";

const OFFLINE_HINT_MS = 20_000;

type RunState = { view: CommandView | null; submitting: boolean; offline: boolean; error: string | null };
const IDLE: RunState = { view: null, submitting: false, offline: false, error: null };

/** Enqueues a command and follows commands/{id} until it is done or failed. Cleans up on unmount. */
function useCommandRunner() {
  const [state, setState] = useState<RunState>(IDLE);
  const cleanup = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    cleanup.current?.();
    cleanup.current = null;
  }, []);

  const alive = useRef(true);
  const seq = useRef(0);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      stop();
    };
  }, [stop]);

  const run = useCallback(
    async (type: CommandType, payload: Record<string, unknown>) => {
      stop();
      const mine = ++seq.current;
      setState({ ...IDLE, submitting: true });
      let acquired = false;
      let unsub: (() => void) | null = null;
      let timer: ReturnType<typeof setTimeout> | null = null;
      const finish = () => {
        if (timer) clearTimeout(timer);
        unsub?.();
        if (acquired) {
          acquired = false;
          releaseLiveAuth();
        }
        if (cleanup.current === finish) cleanup.current = null;
      };
      try {
        const id = await enqueueCommand(type, payload);
        await acquireLiveAuth();
        acquired = true;
        // A newer run started (or we unmounted) while this one was awaiting: drop this subscription.
        if (!alive.current || seq.current !== mine) {
          finish();
          return;
        }
        cleanup.current = finish;
        timer = setTimeout(() => setState((s) => (s.view?.finished ? s : { ...s, offline: true })), OFFLINE_HINT_MS);
        setState({ view: commandResultView({ status: "pending" }), submitting: false, offline: false, error: null });
        unsub = onSnapshot(
          doc(getClientDb(), "commands", id),
          (snap) => {
            const view = commandResultView(snap.data() ?? { status: "pending" });
            setState((s) => ({ ...s, view, offline: view.finished ? false : s.offline }));
            if (view.finished) finish();
          },
          (err) => {
            setState((s) => ({ ...s, error: err.message }));
            finish();
          },
        );
      } catch (e) {
        finish();
        setState({ ...IDLE, error: e instanceof Error ? e.message : "Could not send the command" });
      }
    },
    [stop],
  );

  return { state, run };
}

function Result({ state }: { state: RunState }) {
  const { view } = state;
  return (
    <div aria-live="polite" className="space-y-2">
      {view && (
        <p className="text-sm">
          Status: <strong>{view.label}</strong>
        </p>
      )}
      {state.offline && !state.view?.finished && (
        <p role="status" className="text-sm text-muted-foreground">
          The bridge looks offline - the command will run when it is back.
        </p>
      )}
      {view?.finished && view.text && (
        <pre
          className={`max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-border p-3 text-xs ${
            view.isError ? "text-destructive" : ""
          }`}
        >
          {view.text}
        </pre>
      )}
      <FormMessage error={state.error} />
    </div>
  );
}

function ToolCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3 rounded-md border border-border p-4">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function TestSms() {
  const { state, run } = useCommandRunner();
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("Test message from HRM");
  const [err, setErr] = useState<Record<string, string>>({});
  return (
    <ToolCard title="Send test SMS">
      <form
        className="space-y-3"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          const errs: Record<string, string> = {};
          if (!phone.trim()) errs.phone = "Phone number is required";
          if (!message.trim()) errs.message = "Message is required";
          setErr(errs);
          if (Object.keys(errs).length === 0) void run("test_sms", { phone: phone.trim(), message: message.trim() });
        }}
      >
        <Field label="Phone number" error={err.phone}>
          {(p) => <Input {...p} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />}
        </Field>
        <Field label="Message" error={err.message}>
          {(p) => <Input {...p} value={message} onChange={(e) => setMessage(e.target.value)} />}
        </Field>
        <Button type="submit" disabled={state.submitting}>Send test SMS</Button>
      </form>
      <Result state={state} />
    </ToolCard>
  );
}

function Balance({ defaultCode }: { defaultCode: string }) {
  const { state, run } = useCommandRunner();
  const [code, setCode] = useState(defaultCode);
  const [err, setErr] = useState<string | null>(null);
  return (
    <ToolCard title="Check balance (USSD)">
      <form
        className="space-y-3"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (!code.trim()) return setErr("USSD code is required");
          setErr(null);
          void run("ussd", { code: code.trim() });
        }}
      >
        <Field label="USSD code" help="Prefilled from Bridge settings." error={err}>
          {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} />}
        </Field>
        <Button type="submit" disabled={state.submitting}>Check balance</Button>
      </form>
      <Result state={state} />
    </ToolCard>
  );
}

function Inbox() {
  const { state, run } = useCommandRunner();
  return (
    <ToolCard title="SMS inbox">
      <Button type="button" disabled={state.submitting} onClick={() => void run("read_inbox", {})}>
        Read SMS inbox
      </Button>
      <Result state={state} />
    </ToolCard>
  );
}

function AtCommand() {
  const { state, run } = useCommandRunner();
  const [cmd, setCmd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <ToolCard title="Run AT command (advanced)">
      <form
        className="space-y-3"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (!cmd.trim()) return setErr("Command is required");
          setErr(null);
          void run("at_command", { command: cmd.trim() });
        }}
      >
        <Field label="AT command" help="Sent to the GSM modem as typed, e.g. AT+CSQ. Only use commands you understand." error={err}>
          {(p) => <Input {...p} className="font-mono" value={cmd} onChange={(e) => setCmd(e.target.value)} />}
        </Field>
        <Button type="submit" disabled={state.submitting}>Run AT command</Button>
      </form>
      <Result state={state} />
    </ToolCard>
  );
}

function SyncUsers() {
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <ToolCard title="Device users">
      <Button
        type="button"
        variant="outline"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setMsg(null);
          setError(null);
          try {
            await syncDeviceUsers();
            setMsg("Sync requested. The bridge will pick it up shortly.");
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not request sync");
          } finally {
            setBusy(false);
          }
        }}
      >
        Sync device users
      </Button>
      <FormMessage error={error} ok={msg} />
    </ToolCard>
  );
}

export function GsmTools({ ussdCode }: { ussdCode: string }) {
  return (
    <div className="grid max-w-3xl gap-4">
      <p className="text-sm text-muted-foreground">
        Commands are queued in Firestore and run by the bridge on its next poll, so results can take a few seconds.
      </p>
      <TestSms />
      <Balance defaultCode={ussdCode} />
      <Inbox />
      <AtCommand />
      <SyncUsers />
    </div>
  );
}
