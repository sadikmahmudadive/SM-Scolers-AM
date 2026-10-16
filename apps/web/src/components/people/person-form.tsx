"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { createPerson, deletePerson, updatePerson } from "@/actions/people";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { personFormSchema, type PersonFormValues } from "@/lib/person-form-schema";

const EMPTY: PersonFormValues = {
  id: "",
  name: "",
  kind: "student",
  phone: "",
  fatherPhone: "",
  motherPhone: "",
  className: "",
  section: "",
  departmentId: "",
  managerId: "",
  active: true,
};

type Props = { mode: "create" } | { mode: "edit"; initial: PersonFormValues };
type TextField = Exclude<keyof PersonFormValues, "active" | "kind">;

const selectClass =
  "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function PersonForm(props: Props) {
  const router = useRouter();
  const editing = props.mode === "edit";
  const [serverError, setServerError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PersonFormValues>({
    resolver: zodResolver(personFormSchema),
    defaultValues: props.mode === "edit" ? props.initial : EMPTY,
  });

  async function onSubmit(values: PersonFormValues) {
    setServerError(null);
    try {
      if (props.mode === "edit") {
        // The id is the document key and cannot be changed.
        // The manager is assigned from the Manager section (a validated account), not this form.
        const { id, managerId: _managerId, ...patch } = values;
        void _managerId;
        const r = await updatePerson(id, patch);
        if (!r.ok) return setServerError(r.error);
        router.refresh();
      } else {
        const r = await createPerson(values);
        if (!r.ok) return setServerError(r.error);
        router.push("/people");
      }
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  async function onDelete() {
    if (props.mode !== "edit") return;
    setServerError(null);
    try {
      const r = await deletePerson(props.initial.id);
      if (!r.ok) return setServerError(r.error);
      router.push("/people");
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  const field = (name: TextField, label: string, readOnly = false) => (
    <div className="space-y-1">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        readOnly={readOnly}
        aria-invalid={errors[name] ? true : undefined}
        aria-describedby={errors[name] ? `${name}-error` : undefined}
        {...register(name)}
      />
      {errors[name] && (
        <p id={`${name}-error`} role="alert" className="text-xs text-destructive">
          {errors[name]?.message}
        </p>
      )}
    </div>
  );

  return (
    <div className="max-w-xl space-y-6">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {field("id", "Device user ID", editing)}
        {field("name", "Name")}
        <div className="space-y-1">
          <Label htmlFor="kind">Kind</Label>
          <select id="kind" className={selectClass} {...register("kind")}>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
            <option value="staff">Staff</option>
          </select>
        </div>
        {field("phone", "Phone")}
        {field("fatherPhone", "Father phone")}
        {field("motherPhone", "Mother phone")}
        <div className="grid grid-cols-2 gap-4">
          {field("className", "Class")}
          {field("section", "Section")}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {field("departmentId", "Department ID")}
          {!editing && field("managerId", "Manager ID")}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("active")} /> Active
        </label>
        {serverError && (
          <p role="alert" className="text-sm text-destructive">
            {serverError}
          </p>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : editing ? "Save changes" : "Add person"}
        </Button>
      </form>

      {editing && (
        <section aria-label="Danger zone" className="space-y-2 border-t border-border pt-4">
          {confirmingDelete ? (
            <div role="alertdialog" aria-label="Confirm delete" className="space-y-2 text-sm">
              <p>Delete this person? Their attendance history is kept. This cannot be undone.</p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={onDelete} className="border-destructive text-destructive">
                  Yes, delete
                </Button>
                <Button type="button" variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              className="border-destructive text-destructive"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete person
            </Button>
          )}
        </section>
      )}
    </div>
  );
}
