"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ROLES } from "@hrm/shared";
import { createAccount } from "@/actions/accounts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/settings/shared";
import { createAccountFormSchema, type CreateAccountFormValues } from "@/lib/account-form-schema";
import { PersonPicker, type PersonOption } from "./person-picker";

export function CreateAccountForm({ people, truncated }: { people: PersonOption[]; truncated: boolean }) {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateAccountFormValues>({
    resolver: zodResolver(createAccountFormSchema),
    defaultValues: { email: "", password: "", displayName: "", role: "staff", personId: "" },
  });
  const role = watch("role");

  async function onSubmit(v: CreateAccountFormValues) {
    setServerError(null);
    try {
      const r = await createAccount({
        email: v.email,
        password: v.password,
        displayName: v.displayName || undefined,
        role: v.role,
        personId: v.personId || undefined,
      });
      if (!r.ok) return setServerError(r.error);
      router.push("/accounts");
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  const err = (name: keyof CreateAccountFormValues) =>
    errors[name] && (
      <p id={`${name}-error`} role="alert" className="text-xs text-destructive">
        {errors[name]?.message}
      </p>
    );

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="max-w-xl space-y-4" noValidate>
      <div className="space-y-1">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="off"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
        {err("email")}
      </div>
      <div className="space-y-1">
        <Label htmlFor="displayName">Display name (optional)</Label>
        <Input id="displayName" autoComplete="off" {...register("displayName")} />
        {err("displayName")}
      </div>
      <div className="space-y-1">
        <Label htmlFor="password">Initial password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? "password-error" : undefined}
          {...register("password")}
        />
        {err("password")}
      </div>
      <div className="space-y-1">
        <Label htmlFor="role">Role</Label>
        <select id="role" className={selectClass} {...register("role")}>
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
              label={role === "staff" ? "Person (required)" : "Person (optional)"}
              options={people}
              truncated={truncated}
              value={field.value}
              onChange={field.onChange}
              error={errors.personId?.message}
            />
          )}
        />
      )}
      {role === "guardian" && (
        <p className="text-xs text-muted-foreground">
          Guardian access comes from linking the account to students on each student&apos;s page.
        </p>
      )}
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating..." : "Create account"}
      </Button>
    </form>
  );
}
