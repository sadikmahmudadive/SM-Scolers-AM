"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ROLES } from "@hrm/shared";
import { changeRole, resetPassword, setAccountDisabled } from "@/actions/accounts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/settings/shared";
import {
  changeRoleFormSchema,
  resetPasswordFormSchema,
  type ChangeRoleFormValues,
  type ResetPasswordFormValues,
} from "@/lib/account-form-schema";
import type { AccountRow } from "@/lib/accounts";
import { PersonPicker, type PersonOption } from "./person-picker";

type Panel = null | "role" | "password" | "disable";

function messageOf(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong";
}

function RoleForm({
  row,
  people,
  truncated,
  onDone,
}: {
  row: AccountRow;
  people: PersonOption[];
  truncated: boolean;
  onDone: () => void;
}) {
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ChangeRoleFormValues>({
    resolver: zodResolver(changeRoleFormSchema),
    defaultValues: { role: row.role ?? "staff", personId: row.personId ?? "" },
  });
  const role = watch("role");
  async function onSubmit(v: ChangeRoleFormValues) {
    setServerError(null);
    try {
      const r = await changeRole(row.uid, v.role, v.personId || undefined);
      if (!r.ok) return setServerError(r.error);
      onDone();
    } catch (e) {
      setServerError(messageOf(e));
    }
  }
  const selId = `role-${row.uid}`;
  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      aria-label={`Change role for ${row.email}`}
      className="w-72 space-y-2 rounded-md border border-border p-3"
      noValidate
    >
      <div className="space-y-1">
        <Label htmlFor={selId}>Role</Label>
        <select id={selId} className={selectClass} {...register("role")}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>
      {role !== "guardian" && (
        <Controller
          control={control}
          name="personId"
          render={({ field }) => (
            <PersonPicker
              label={role === "staff" ? "Linked person (required)" : "Linked person (optional)"}
              options={people}
              truncated={truncated}
              value={field.value}
              onChange={field.onChange}
              error={errors.personId?.message}
            />
          )}
        />
      )}
      {serverError && (
        <p role="alert" className="text-xs text-destructive">
          {serverError}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Save role"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function PasswordForm({ row, onDone }: { row: AccountRow; onDone: () => void }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordFormSchema),
    defaultValues: { password: "" },
  });
  async function onSubmit(v: ResetPasswordFormValues) {
    if (!confirming) return setConfirming(true);
    setServerError(null);
    try {
      const r = await resetPassword(row.uid, v.password);
      if (!r.ok) {
        setConfirming(false);
        return setServerError(r.error);
      }
      onDone();
    } catch (e) {
      setConfirming(false);
      setServerError(messageOf(e));
    }
  }
  const id = `pw-${row.uid}`;
  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      aria-label={`Reset password for ${row.email}`}
      className="w-72 space-y-2 rounded-md border border-border p-3"
      noValidate
    >
      <div className="space-y-1">
        <Label htmlFor={id}>New password</Label>
        <Input
          id={id}
          type="password"
          autoComplete="new-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? `${id}-err` : undefined}
          readOnly={confirming}
          {...register("password")}
        />
        {errors.password && (
          <p id={`${id}-err`} role="alert" className="text-xs text-destructive">
            {errors.password.message}
          </p>
        )}
      </div>
      {confirming && (
        <p role="alertdialog" aria-label="Confirm password reset" className="text-xs">
          Set this password and sign the user out everywhere?
        </p>
      )}
      {serverError && (
        <p role="alert" className="text-xs text-destructive">
          {serverError}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={isSubmitting}>
          {confirming ? "Yes, reset password" : "Reset password"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function RowActions({
  row,
  isSelf,
  people,
  truncated,
}: {
  row: AccountRow;
  isSelf: boolean;
  people: PersonOption[];
  truncated: boolean;
}) {
  const router = useRouter();
  const [panel, setPanel] = useState<Panel>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const close = () => {
    setPanel(null);
    router.refresh();
  };

  async function toggleDisabled(disabled: boolean) {
    setError(null);
    setBusy(true);
    try {
      const r = await setAccountDisabled(row.uid, disabled);
      if (!r.ok) return setError(r.error);
      setPanel(null);
      router.refresh();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        <Button type="button" size="sm" variant="outline" onClick={() => setPanel(panel === "role" ? null : "role")}>
          Role
          <span className="sr-only"> for {row.email}</span>
        </Button>
        {row.disabled ? (
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => toggleDisabled(false)}>
            Enable<span className="sr-only"> {row.email}</span>
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isSelf}
            onClick={() => setPanel(panel === "disable" ? null : "disable")}
          >
            Disable<span className="sr-only"> {row.email}</span>
          </Button>
        )}
        <Button type="button" size="sm" variant="outline" onClick={() => setPanel(panel === "password" ? null : "password")}>
          Reset password<span className="sr-only"> for {row.email}</span>
        </Button>
      </div>
      {panel === "role" && <RoleForm row={row} people={people} truncated={truncated} onDone={close} />}
      {panel === "password" && <PasswordForm row={row} onDone={close} />}
      {panel === "disable" && (
        <div role="alertdialog" aria-label="Confirm disable" className="w-72 space-y-2 rounded-md border border-border p-3 text-xs">
          <p>Disable {row.email}? They are signed out everywhere and cannot sign in.</p>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="border-destructive text-destructive"
              disabled={busy}
              onClick={() => toggleDisabled(true)}
            >
              Yes, disable
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setPanel(null)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function formatTime(iso: string | null): string {
  if (!iso) return "never";
  return iso.slice(0, 16).replace("T", " ") + " UTC";
}

export function AccountsTable({
  rows,
  currentUid,
  people,
  truncated,
}: {
  rows: AccountRow[];
  currentUid: string;
  people: PersonOption[];
  truncated: boolean;
}) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No accounts yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th scope="col" className="py-1">Email</th>
            <th scope="col">Name</th>
            <th scope="col">Role</th>
            <th scope="col">Linked person</th>
            <th scope="col">Status</th>
            <th scope="col">Last sign-in</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.uid} className="border-b border-border align-top">
              <td className="py-2">{r.email || "-"}</td>
              <td>{r.displayName || "-"}</td>
              <td className={r.role ? "" : "text-destructive"}>{r.roleLabel}</td>
              <td>
                {r.personId ? `${r.personId}${r.personName ? ` - ${r.personName}` : " (person not found)"}` : "-"}
              </td>
              <td>{r.disabled ? "Disabled" : "Enabled"}</td>
              <td>{formatTime(r.lastSignIn)}</td>
              <td>
                <RowActions row={r} isSelf={r.uid === currentUid} people={people} truncated={truncated} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
