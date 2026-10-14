import { CircleAlert } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

/** The card every auth page uses: title, short explanation, the form, and links underneath. */
export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    // A thin teal-to-cyan line across the top ties the card to the brand (D-62, D-64).
    // "stagger" (globals.css): the Google button, the form fields and the button fade up one after another.
    <Card className="relative overflow-hidden rounded-2xl shadow-xl shadow-slate-900/5">
      <span className="absolute inset-x-0 top-0 h-1 bg-linear-to-r from-teal-500 via-cyan-400 to-teal-500" aria-hidden />
      <CardHeader className="pt-2">
        <CardTitle className="text-2xl tracking-tight">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="stagger flex flex-col gap-5">{children}</CardContent>
      {footer && <CardFooter className="justify-center text-sm text-muted-foreground">{footer}</CardFooter>}
    </Card>
  );
}

/** The API's own message ("Incorrect email or password") above the form. Announced by screen readers. */
export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

/** "or" line between the Google button and the email form. */
export function OrDivider() {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground uppercase">
      <span className="h-px flex-1 bg-border" />
      or
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}
