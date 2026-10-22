import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

/**
 * Landing page FAQ (DECISIONS D-65), on shadcn's Accordion. Every answer describes what the product does
 * today; the comment on each names the rule or feature behind it, for the viva.
 */
const QUESTIONS = [
  {
    q: "Does ReconcilePro move my money?",
    // Statements are read-only imports; Paystack pays the business's own Paystack account.
    a: "No. It reads the bank statements you upload and the Paystack payments your customers make, then records which invoice each one paid. Your money stays in your bank and Paystack accounts.",
  },
  {
    q: "Which bank statements can I import?",
    // statements/parsers: bank_a and bank_b, detected from the header row.
    a: "CSV exports in the two statement layouts it recognises today. It finds the header row by itself, even with account details above it. Supporting another layout is one small parser.",
  },
  {
    q: "What if the same statement is uploaded twice?",
    // Invariant 2: unique (workspace_id, fingerprint) + INSERT … ON CONFLICT DO NOTHING.
    a: "Nothing is added twice. Every bank line gets a fingerprint, and a line already imported is skipped, so overlapping statements are safe.",
  },
  {
    q: "What happens when a match is wrong?",
    // Invariant 7: reversed_at, never deleted; audit_events row with the reason.
    a: "You reverse it with a reason. The payment goes back to the review queue, the invoice's balance is restored, and the original record stays in the audit log. Nothing is ever deleted.",
  },
  {
    q: "How do customers pay?",
    // Public invoice page /i/{token}, Paystack checkout, bank details (D-58, D-61).
    a: "Each invoice has its own link. Customers pay by card through Paystack, or by bank transfer to the account you save in Settings, quoting the invoice reference so it is matched automatically.",
  },
  {
    q: "Is VAT handled?",
    // VAT 7.5% on the subtotal, rounded half up to the kobo (backend rules).
    a: "Yes. VAT at 7.5% is worked out on the server for every invoice, to the exact kobo.",
  },
];

export function Faq() {
  return (
    <Accordion type="single" collapsible className="w-full rounded-2xl bg-card px-6 shadow-card">
      {QUESTIONS.map((item, index) => (
        <AccordionItem key={item.q} value={`q${index}`}>
          <AccordionTrigger className="py-5 text-left font-heading text-base font-extrabold">{item.q}</AccordionTrigger>
          <AccordionContent className="text-muted-foreground">{item.a}</AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
