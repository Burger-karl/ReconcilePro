"use client";

import { Controller, type Control, type FieldValues, type Path } from "react-hook-form";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

/**
 * One labelled input wired to react-hook-form: label above, help text, error under the field
 * (design-system MASTER.md §4: visible labels, never placeholder-only).
 */
export function TextField<T extends FieldValues>({
  control,
  name,
  label,
  type = "text",
  autoComplete,
  description,
}: {
  control: Control<T>;
  name: Path<T>;
  label: string;
  type?: "text" | "email" | "password";
  autoComplete?: string;
  description?: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={name}>{label}</FieldLabel>
          {/* 16px text so phones don't zoom in when the field is focused (MASTER.md §2). */}
          <Input
            {...field}
            id={name}
            type={type}
            autoComplete={autoComplete}
            aria-invalid={fieldState.invalid}
            className="text-base"
          />
          {description && !fieldState.invalid && <FieldDescription>{description}</FieldDescription>}
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}
