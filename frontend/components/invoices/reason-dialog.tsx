"use client";

/**
 * Confirm an action that needs a written reason: voiding an invoice, reversing a payment.
 * MASTER.md §4 asks for an alert-dialog here: these are deliberate, recorded actions (invariant 7: the
 * reason is stored with the audit event, and nothing is ever deleted).
 */

import { useState } from "react";

import { FormError } from "@/components/auth/auth-card";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";

export function ReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  /** Does the API call. Throwing keeps the dialog open and shows the API's message. */
  onConfirm: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function confirm() {
    if (!reason.trim()) {
      setError("Write a short reason: it is kept in the audit log.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setReason("");
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setError(null);
        onOpenChange(next);
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <FormError message={error} />
        <div className="flex flex-col gap-2">
          <Label htmlFor="reason">Reason</Label>
          <Textarea
            id="reason"
            value={reason}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            className="text-base"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
          {/* A plain Button, not AlertDialogAction: that one closes the dialog before the API has answered. */}
          <Button variant="destructive" onClick={() => void confirm()} disabled={saving}>
            {saving ? "Saving…" : confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
