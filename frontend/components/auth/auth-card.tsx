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
    // CEK style (D-71): a white card with 20px corners and a soft shadow on the beige page.
    // "stagger" (globals.css): the Google button, the form fields and the button fade up one after another.
    <Card className="rounded-3xl py-8">
      <CardHeader className="px-8">
        <CardTitle className="text-3xl font-black tracking-tight">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="stagger flex flex-col gap-5 px-8">{children}</CardContent>
      {footer && <CardFooter className="justify-center bg-transparent px-8 text-sm text-muted-foreground">{footer}</CardFooter>}
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
