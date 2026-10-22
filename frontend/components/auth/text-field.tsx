"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Controller, type Control, type FieldValues, type Path } from "react-hook-form";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";

/**
 * One labelled input wired to react-hook-form: label above, help text, error under the field
 * (design-system MASTER.md §4: visible labels, never placeholder-only).
 *
 * A password field gets an eye button (shadcn input-group) that shows or hides what was typed, so people can
 * check a password before submitting it. It starts hidden, and the button says which way it will switch.
 */
export function TextField<T extends FieldValues>({
  control,
  name,
  label,
  type = "text",
  autoComplete,
  description,
  inputMode,
}: {
  control: Control<T>;
  name: Path<T>;
  label: string;
  type?: "text" | "email" | "password" | "date";
  autoComplete?: string;
  description?: string;
  /** Which on-screen keyboard phones show, e.g. "numeric" for an account number. */
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  const [passwordShown, setPasswordShown] = useState(false);

  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={name}>{label}</FieldLabel>
          {type === "password" ? (
            <InputGroup>
              {/* 16px text so phones don't zoom in when the field is focused (MASTER.md §2). */}
              <InputGroupInput
                {...field}
                id={name}
                // Switching the type is all it takes: the value stays in react-hook-form either way.
                type={passwordShown ? "text" : "password"}
                autoComplete={autoComplete}
                aria-invalid={fieldState.invalid}
                className="text-base"
              />
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  size="icon-xs"
                  className="rounded-full"
                  aria-label={passwordShown ? "Hide password" : "Show password"}
                  aria-pressed={passwordShown}
                  onClick={() => setPasswordShown((shown) => !shown)}
                >
                  {passwordShown ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
          ) : (
            <Input
              {...field}
              id={name}
              type={type}
              autoComplete={autoComplete}
              inputMode={inputMode}
              aria-invalid={fieldState.invalid}
              className="text-base"
            />
          )}
          {description && !fieldState.invalid && <FieldDescription>{description}</FieldDescription>}
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}
