# Testing ReconcilePro in the browser

A step-by-step check of every feature from the UI. Tick each box as you go. Each step says what to do and what
you should see. If what you see is different, note the step number and what happened.

Takes about 45 minutes. Do the sections in order: later ones use data from earlier ones.

---

## 0. Before you start

1. **Start the three servers** (each in its own terminal, so low memory can't stop them):
   - Postgres on port 54687 (see the commands from the session, or ask Claude to start it).
   - API:
     ```powershell
     cd C:\Users\charl\Desktop\Projects\ReconcilePro\backend
     $env:ENVIRONMENT="development"; $env:DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:54687/reconcile_test"
     .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
     ```
   - Web:
     ```powershell
     cd C:\Users\charl\Desktop\Projects\ReconcilePro\frontend
     npm start -- -p 3000
     ```
2. Open <http://localhost:3000> in Chrome and press **Ctrl+Shift+R** once.
3. Keep **DevTools → Console** open (F12). Any red error is worth noting.

**Demo data.** The demo workspace "Adaeze Foods" has 6 customers, 8 invoices and one imported statement.
Sign in with `demo@adaezefoods.ng` / `demo-password-1`.

> **Running the backend tests wipes this data** (they share the database). To get it back:
> ```powershell
> cd C:\Users\charl\Desktop\Projects\ReconcilePro\backend
> $env:ENVIRONMENT="development"; $env:DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:54687/reconcile_test"
> .venv\Scripts\python.exe seed.py
> ```

**What can't be fully tested on localhost**
- **Emails** (invoice links, password reset) are not delivered locally: the Resend key here is rejected. The
  app still works; the email step just fails quietly. Check the API terminal for the email error.
- **Paystack**: you can reach Paystack's checkout, but Paystack can't call back to `localhost`, so the invoice won't
  turn "Paid" by itself. That part is tested after deploying (section 13).
- **Google sign-in** only shows once a client ID is set up (`docs/GOOGLE-SIGN-IN.md`).

---

## 1. Landing page and theme

- [ ] **1.1** Open <http://localhost:3000>. The landing page loads with a mint-tinted background (not plain white)
      and coloured cards in "Why switch", "How it works", "Built for money", "Who it's for" and the FAQ.
- [ ] **1.2** Click the **theme toggle** (sun/moon). The page switches to dark mode: deep teal-navy, cards with
      faint coloured glows. Switch back.
- [ ] **1.3** Click each tab in **Who it's for** (Business owner, Accountant, Your customer). The card text changes.
- [ ] **1.4** Open and close a few **FAQ** questions.
- [ ] **1.5** Make the window narrow (or DevTools → phone icon, 375px wide). Nothing is cut off and there's no
      sideways scrolling.

## 2. Register a new workspace

Use a fresh email so the demo workspace stays clean.

- [ ] **2.1** Click **Create free workspace** (or go to `/register`).
- [ ] **2.2** Click **Create workspace** with every field empty. Each field shows an error; nothing is sent.
- [ ] **2.3** Enter business name `Test Traders`, email `you+test1@example.com`, and a short password like `abc`.
      You're told the password is too short.
- [ ] **2.4** Use a proper password (8+ characters) and submit. You land on the **dashboard** of the new, empty
      workspace.
- [ ] **2.5** Sign out (your account menu at the bottom of the left rail → **Sign out**). Try to register **the same email again**: you're told an account
      with this email already exists.

## 3. Sign in, sign out, protection

- [ ] **3.1** Go to `/login`. Enter the demo email with a **wrong** password. You see one message that doesn't say
      whether the email or the password was wrong.
      > Don't do this 10 times: after 10 wrong passwords that email is locked for 15 minutes (on purpose).
- [ ] **3.2** Sign in with the right password. You land on `/dashboard`.
- [ ] **3.3** While signed in, open `/login`. You see "You're already signed in as …" with a button to the dashboard.
- [ ] **3.4** Sign out. Then type <http://localhost:3000/invoices> in the address bar. You're sent to `/login`, and
      after signing in you come back to **Invoices**.
- [ ] **3.5** Open the site in a second tab and sign in. Sign out in the first tab, then click around in the second:
      within a click or two it sends you to `/login` (sign-out ends every session).

## 4. Forgot password

- [ ] **4.1** On `/login` click **Forgot your password?**, enter any email, submit. You get the same "check your email"
      message whether or not the account exists.
- [ ] **4.2** Optional: the reset link isn't emailed locally. If the API runs with no Resend key, the link is printed
      in the API terminal; open it, choose a new password, and sign in with it. Old sessions are signed out.

## 5. Dashboard (Overview)

Sign in as the **demo** user.

- [ ] **5.1** The tiles show **Outstanding**, **Collected this month**, **Auto-match rate** and **Needs review**,
      all with naira amounts like `₦1,234,500.00`.
- [ ] **5.2** The **collections** chart shows weekly bars; hover one to see its amount.
- [ ] **5.3** The **ageing** list shows Current, 1–30, 31–60 and 60+ days, each with an amount and count.
- [ ] **5.4** Note the **Needs review** number; you'll see it change in section 9.

## 6. Customers

- [ ] **6.1** Open **Customers**. Six demo customers are listed, each with what they still owe.
- [ ] **6.2** Search `kola`. Only "Kola & Sons" is left. Clear the search.
- [ ] **6.3** **Add customer**: name `Femi Ventures`, email `femi@example.com`, aliases on separate lines:
      `FEMI VENTURES` and `FEMI V`. Save. It appears in the list.
- [ ] **6.4** Try adding a customer with email `not-an-email`. You're told the email isn't valid.
- [ ] **6.5** Click **Femi Ventures**, change the phone number, **Save changes**. The change sticks after a reload.

## 7. Invoices

- [ ] **7.1** Open **Invoices**. The list shows statuses with colours: **paid** green, **part paid** amber, **overdue**
      red, **sent** blue, **draft** grey.
- [ ] **7.2** **Filter by status** → Overdue. Only overdue invoices remain. Clear the filter.
- [ ] **7.3** **New invoice** for **Femi Ventures**: description `October supplies`, subtotal `100000`, issue date
      today, due date in 14 days. **Save draft**. VAT shows `₦7,500.00` and the total `₦107,500.00`.
- [ ] **7.4** Open the draft and change the subtotal to `200000`. VAT and total update to `₦15,000.00` /
      `₦215,000.00`.
- [ ] **7.5** **Send invoice** and confirm. The status becomes **sent**. Note the invoice **number** and **payment
      reference** (looks like `RCN-XXXXXX`); you'll need the reference in section 8.
- [ ] **7.6** After sending, the invoice can no longer be edited.
- [ ] **7.7** **Email** it again: you're told it was sent to `femi@example.com` (it won't actually arrive locally).
- [ ] **7.8** Create a second draft for any customer and **Void invoice** with a reason. It shows as **void**.
- [ ] **7.9** Open a **paid** demo invoice (Kola & Sons). **Void** isn't allowed: it says to reverse its payments first.

## 8. Import a bank statement

Make a small CSV in Notepad and save it as `test-statement.csv` (Save as type: **All files**). Replace
`RCN-XXXXXX` with the reference from step 7.5, and use dates from this month in the same `YYYY/MM/DD` format:

```csv
DATE POSTED,VALUE DATE,DESCRIPTION,DEBIT,CREDIT
2026/10/20,2026/10/20,NIP/FEMI VENTURES/RCN-XXXXXX,,215000.00
2026/10/21,2026/10/21,NIP/FEMI V/SUPPLIES,,50000.00
2026/10/21,2026/10/21,PAYSTACK SETTLEMENT 0099887,,120000.00
2026/10/21,2026/10/21,NIP/UNKNOWN PAYER/TRANSFER,,7500.00
2026/10/22,2026/10/22,POS PURCHASE SHOPRITE,4500.00,
```

- [ ] **8.1** Open **Statements** → **Import a bank statement** → choose the file → **Import**.
- [ ] **8.2** The summary shows: 4 lines added, **1 settlement**, **1 debit ignored**, **1 matched automatically**
      (the one quoting your reference), and the rest needing review.
- [ ] **8.3** Open **Invoices**: your Femi invoice is now **paid**.
- [ ] **8.4** **Import the same file again.** It adds **0** lines and reports **4 duplicates skipped**.
- [ ] **8.5** In the statement ledger, click the settlement line: it is marked as a **Paystack payout** and is not
      matched to any invoice.
- [ ] **8.6** Try importing a file that isn't a CSV (e.g. a `.txt` with random text). You get a clear error and nothing
      is imported.

## 9. Match screen (the exception queue)

- [ ] **9.1** Open **Match**. The left list shows payments that need a person. Each shows its narration in a
      monospace font and the amount.
- [ ] **9.2** Select `NGOZI CATERING/INVOICE PAYMENT`. On the right, likely invoices appear, best first, each with a
      score and plain-English reasons (amount equals what's owed, payer name similar, paid N days after sending).
- [ ] **9.3** Click **Accept** on the top suggestion. The payment leaves the queue and the **Needs review** count drops.
- [ ] **9.4** Click **Undo** on the confirmation. The payment comes back to the queue.
- [ ] **9.5** Select `ADEBAYO OKON/TRANSFER`, then **Not this one** on a candidate. That candidate disappears for this
      payment and doesn't come back after a reload.
- [ ] **9.6** Select the `FEMI V/SUPPLIES` (₦50,000) line → **Allocate part…** / **Match to an invoice** → choose a
      Femi or other open invoice and enter `20000`. The payment stays in the queue with ₦30,000 left.
- [ ] **9.7** Try to allocate **more** than the payment has left, or more than the invoice owes. You're stopped with a
      clear message.
- [ ] **9.8** Keyboard: press `?` to see the shortcuts. Try `j` / `k` (next / previous), `1`–`3` (pick a candidate),
      `a` (accept), `r` (reject), `m` (match by hand).

## 10. Reversing a payment

- [ ] **10.1** Open the invoice you matched in 9.3 (or Emeka Farms). Under **Payments**, click **Reverse payment**,
      give a reason, confirm.
- [ ] **10.2** The payment shows as reversed (with your reason), still listed, not deleted. The invoice's status goes
      back to **sent** or **overdue**, and the bank line is back on the Match screen.

## 11. Audit log

- [ ] **11.1** Open **Audit log**. Your actions from today are there, newest first, as plain sentences: invoice
      created, sent, voided, payment matched, reversed, match rejected, customer edited, statement imported.
- [ ] **11.2** Each shows **who** did it (your email) or **System** for automatic matches.
- [ ] **11.3** Click an event to see its details (for an edit: before and after).
- [ ] **11.4** **Filter by what changed** → Invoices. Only invoice events remain.

## 12. Settings and the public invoice page

- [ ] **12.1** Open **Settings**. Enter a bank name, a 10-digit account number and an account name; **Save bank
      details**. A 9-digit number is refused.
- [ ] **12.2** Open a **sent** invoice → **Copy payment link**. Open it in a **private window** (not signed in).
- [ ] **12.3** The public page shows your business name, the invoice, the amount owed, the payment reference, and
      the bank details from 12.1 with **Copy** buttons. Nothing else from your workspace is shown.
- [ ] **12.4** Make the private window phone-sized (375px). Everything fits and is readable.
- [ ] **12.5** Open a **paid** invoice's link: it says it's paid and offers no Pay button.
- [ ] **12.6** Change one character in the link's token and open it: "Invoice not found".

## 13. Paystack online payment

- [ ] **13.1** On the public page of an unpaid invoice whose customer has an email, click **Pay**. If the API has a
      Paystack **test** secret key, you're taken to Paystack's checkout for the amount owed.
      (Without a key you get a clear "unavailable" message.)
- [ ] **13.2** Pay with Paystack's test card `4084 0840 8408 4081`, any future expiry, CVV `408`, PIN `0000`,
      OTP `123456`. You're sent back to the invoice page.
- [ ] **13.3** **Locally** the invoice stays unpaid: Paystack's webhook can't reach `localhost`. **After deploying**,
      with the webhook set to `https://<api>/api/v1/webhooks/paystack`, the page turns **Paid** within a few
      seconds, the payment appears on the invoice and in the audit log, and the dashboard's "Collected" goes up.
- [ ] **13.4** For an invoice whose customer has **no email**, Pay explains that an email is needed.

## 14. Installable app (PWA)

- [ ] **14.1** In Chrome, use the install icon in the address bar, or ⋮ → **Cast, save, and share** → **Install
      page as app**. It opens in its own window at the dashboard.
- [ ] **14.2** DevTools → **Application** → **Manifest**: name, icons, no errors. **Service workers**: `/sw.js` is
      activated.
- [ ] **14.3** DevTools → **Network** → set to **Offline**, reload. You see "You're offline". Set back to
      **No throttling**, click **Try again**: the app returns.

## 15. Security checks you can see

- [ ] **15.1** As the demo user, copy an invoice's URL (e.g. `/invoices/<id>`). Sign in as the **Test Traders** user
      from section 2 and open that URL. You get "not found": one workspace can't see another's data.
- [ ] **15.2** DevTools → **Console** on any page: no red "Content-Security-Policy" errors.
- [ ] **15.3** Leave the app signed in for over **2 hours** (or come back later): the next click sends you to
      `/login` (tokens last 2 hours).

## 16. Google sign-in (only once set up)

- [ ] **16.1** After following `docs/GOOGLE-SIGN-IN.md`, `/register` and `/login` show a Google button.
- [ ] **16.2** Register a new workspace with Google, sign out, and sign back in with Google.

---

## Results

| Section | Pass / fail | Notes |
| --- | --- | --- |
| 1 Landing and theme | | |
| 2 Register | | |
| 3 Sign in / out | | |
| 4 Forgot password | | |
| 5 Dashboard | | |
| 6 Customers | | |
| 7 Invoices | | |
| 8 Statement import | | |
| 9 Match screen | | |
| 10 Reversal | | |
| 11 Audit log | | |
| 12 Settings and public page | | |
| 13 Paystack | | |
| 14 PWA | | |
| 15 Security | | |
| 16 Google | | |
