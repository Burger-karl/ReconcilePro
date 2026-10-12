"use client";

/**
 * Upload a bank statement CSV (slice F6). The server does all the work in one database transaction
 * (backend D-20): it recognises the bank format, stores each money-in line once (a line already imported
 * is skipped, invariant 2), marks Paystack payouts as settlements (invariant 6), and matches exact
 * references straight away. This card only sends the file and explains the result.
 */

import { CircleAlert, FileUp, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { useSWRConfig } from "swr";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { refreshAfterChange } from "@/lib/refresh";

type Result = Schemas["ImportResult"];

// Same limit as the API (statements/service.py MAX_FILE_BYTES), checked here only to answer faster.
const MAX_BYTES = 5 * 1024 * 1024;

export function UploadCard() {
  const { mutate } = useSWRConfig();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  function choose(chosen: File | undefined) {
    setResult(null);
    setError(null);
    if (!chosen) return setFile(null);
    if (chosen.size > MAX_BYTES) {
      setFile(null);
      return setError("That file is larger than 5 MB. Export a shorter period, e.g. one month.");
    }
    setFile(chosen);
  }

  async function upload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      setResult(await api<Result>(`${API}/statements/import`, { method: "POST", body: form }));
      setFile(null);
      if (input.current) input.current.value = "";
      await refreshAfterChange(mutate);
    } catch (caught) {
      // e.g. "Line 7: the reference is longer than 100 characters": nothing was imported (all or nothing).
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Import a bank statement</CardTitle>
        <CardDescription>
          A CSV exported from your bank (up to 5 MB). Importing the same statement twice adds nothing, so overlapping
          exports are safe.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={input}
            id="statement-file"
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(event) => choose(event.target.files?.[0])}
          />
          <Button asChild variant="outline">
            <label htmlFor="statement-file" className="cursor-pointer">
              <FileUp aria-hidden />
              Choose CSV file
            </label>
          </Button>
          <span className="min-w-0 truncate text-sm text-muted-foreground">{file ? file.name : "No file chosen"}</span>
          <Button onClick={() => void upload()} disabled={!file || uploading} className="sm:ml-auto">
            <Upload aria-hidden />
            {uploading ? "Importing…" : "Import"}
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertDescription>
              {/* The API's message may not end with a full stop; add one so the two sentences don't run together. */}
              {error.replace(/\.?\s*$/, ".")} Nothing from this file was imported, so you can fix it and try again.
            </AlertDescription>
          </Alert>
        )}

        {result && (
          <div role="status" className="rounded-lg border bg-canvas p-4 text-sm">
            <p className="font-medium">
              Imported from a {result.bank.replace("_", " ").toUpperCase()} statement: {result.added} new money-in line
              {result.added === 1 ? "" : "s"}.
            </p>
            <ul className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
              <li>{result.rows_read} lines read</li>
              <li>{result.skipped_duplicates} already imported before (skipped)</li>
              <li>{result.auto_allocated} matched to invoices automatically</li>
              <li>{result.settlements} Paystack payouts (never matched)</li>
              <li>{result.debits_ignored} money-out lines ignored</li>
              <li className="font-medium text-foreground">{result.needs_review} need you</li>
            </ul>
            {result.needs_review > 0 && (
              <Button asChild size="sm" className="mt-3">
                <Link href="/match">Match {result.needs_review} payment{result.needs_review === 1 ? "" : "s"}</Link>
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
