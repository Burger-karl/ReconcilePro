# Setting up "Sign in with Google"

The code is already built (DECISIONS D-37, D-38, D-46). It stays switched off until you give it a
**client ID** from Google Cloud Console. This guide gets you one and plugs it in, first locally and then on
Vercel and Render.

How it works, in one paragraph: the browser loads Google's script (`accounts.google.com/gsi/client`), which
draws the button. When someone picks an account, Google hands the browser an **ID token** (a JWT signed by
Google). The frontend posts it to `POST /api/v1/auth/google/login` or `/google/register`, and
`backend/app/auth/google.py` checks Google's signature and that the token was issued **for our client ID**
(`aud`). No redirect and no client secret are involved. That's why you only need the client ID, in two places.

---

## 1. Create (or pick) a Google Cloud project

1. Go to <https://console.cloud.google.com/> and sign in with the Google account that should own the app.
2. Click the project picker in the top bar, then **New project**.
3. Name it `ReconcilePro`, click **Create**, and make sure it is the selected project.

## 2. Set up the consent screen (Google Auth Platform → Branding)

This is what people see in Google's popup ("Sign in to ReconcilePro").

1. Open **Google Auth Platform → Branding**: <https://console.cloud.google.com/auth/branding>.
   On a new project it shows **Get started**. Click it.
2. **App information:** app name `ReconcilePro`, and your email as the **User support email**.
3. **Audience:** choose **External**, which means any Google account, not only one company's Workspace.
4. **Contact information:** your email. Agree to the policy, then click **Create**.
5. Optional: under **Branding**, upload the logo (`frontend/app/icon.png`) and add homepage and
   privacy-policy links. Links must be on an **authorised domain**, so add your Vercel domain once you have it.

## 3. Scopes (Data Access)

Nothing to add. Sign-in uses the default scopes `openid`, `email` and `profile`, which need no Google
review. Leave <https://console.cloud.google.com/auth/scopes> as it is.

## 4. Who may sign in (Audience)

A new app is in **Testing** status. **Only the accounts listed as test users can sign in.** Everyone else
gets an "access blocked" error from Google.

- For local development: open **Audience**
  (<https://console.cloud.google.com/auth/audience>), go to **Test users**, then **Add users**, and add your
  own Gmail and anyone demoing with you.
- For the deployed demo (instructor, testers): click **Publish app** on the same page to move it to
  **In production**. With only the default scopes, Google doesn't need to verify the app first.

## 5. Create the client ID (Clients)

1. Open **Google Auth Platform → Clients**: <https://console.cloud.google.com/auth/clients>.
2. Click **Create client**.
3. **Application type:** `Web application`. **Name:** `ReconcilePro web`.
4. **Authorised JavaScript origins:** the addresses the button runs on. Use the scheme and host only: no path
   and no trailing `/`. Google asks for both of the localhost entries:

   | Origin | When |
   | --- | --- |
   | `http://localhost` | local |
   | `http://localhost:3000` | local (`npm run dev` / `npm start`) |
   | `https://<your-app>.vercel.app` | after deploying (step 8) |

5. **Authorised redirect URIs:** leave this **empty**. Our button sends the token to JavaScript, not to a
   redirect URL.
6. Click **Create**. Copy the **Client ID**, which looks like
   `1234567890-abc123def456.apps.googleusercontent.com`.

> Google also shows a **client secret**. We don't use it, so don't put it in any `.env` file or commit it. The
> client ID is not a secret: it ends up in the page's JavaScript anyway.

New or changed origins can take a few minutes, and sometimes longer, to start working.

## 6. Plug it in locally

The **same** client ID goes in both places. The backend refuses tokens issued for any other ID (the `aud`
check).

**Frontend:** `frontend/.env.local` (create it if missing; it is git-ignored):

```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=1234567890-abc123def456.apps.googleusercontent.com
```

**Backend:** `backend/.env`:

```env
GOOGLE_CLIENT_ID=1234567890-abc123def456.apps.googleusercontent.com
```

Then restart both:

1. **API:** stop uvicorn and start it again. Settings are read once at startup (`app/core/config.py`).
2. **Web:** `NEXT_PUBLIC_*` values are copied into the JavaScript **when it is built**.
   - `npm run dev`: stop it and start it again.
   - `npm start`: run `npm run build -- --webpack` first, then `npm start -- -p 3000`.

## 7. Check it works

1. Open <http://localhost:3000/register>. A Google button appears above the form, with an "or" line.
   No button means the frontend was built without the client ID (step 6, web).
2. Enter a workspace name, click the Google button, and pick an account that is a test user (step 4).
3. You land on `/dashboard`, signed in to a new workspace.
4. Sign out, go to `/login`, and click the Google button. You are signed straight back in.
5. Open the browser console (F12). There should be no red `Content-Security-Policy` errors mentioning
   `accounts.google.com`. Google's script is allowed in `frontend/next.config.ts`.

## 8. Production (Vercel + Render)

1. Deploy first, so you know the exact Vercel URL.
2. Go back to **Clients**, open `ReconcilePro web`, add `https://<your-app>.vercel.app` to **Authorised
   JavaScript origins**, and click **Save**. Origins must match exactly, with no wildcards. Vercel *preview* URLs
   (`…-git-branch-….vercel.app`) are different origins, so the button won't work there unless you add them too.
3. **Vercel** → Project → Settings → Environment Variables: add `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, then
   **redeploy**. A variable added after a build is not in that build.
4. **Render** → API service → Environment: add `GOOGLE_CLIENT_ID` with the same value. Render restarts the
   service.
5. If the instructor or testers will sign in, click **Publish app** (step 4).

## Troubleshooting

| What you see | Cause | Fix |
| --- | --- | --- |
| No Google button | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` was empty when the frontend was built | Set it, rebuild or restart the web app |
| Popup: "Error 400: origin_mismatch" or console: "The given origin is not allowed for the given client ID" | The page's origin isn't in **Authorised JavaScript origins** | Add it exactly (scheme + host + port), wait a few minutes |
| Popup: "Access blocked … has not completed the Google verification process" | App is in **Testing** and this account isn't a test user | Add the account under **Audience → Test users**, or **Publish app** |
| Error above the form: "Google sign-in is not configured" (API 503) | `GOOGLE_CLIENT_ID` is empty on the API | Set it in `backend/.env` or on Render, restart the API |
| Error: "Google sign-in failed" (API 401) | The token's `aud` doesn't match: the frontend and backend have **different** client IDs. Or the server clock is wrong, so the token looks expired | Use the same ID in both; check the clock |
| Error: "Google sign-in is unavailable, try again" (API 503) | The API couldn't download Google's public keys | Check the API's internet access; try again |
| Error: "No account is linked to this Google account…" on **Sign in** (401) | No ReconcilePro account uses that Google account or its email | Register with Google first |
| Error: "An account with this email already exists" on **Register** (409) | That email already has an account | Use **Sign in** instead. A password account with the same Gmail is linked on first Google sign-in, and its password is removed (D-38, D-46) |
| Console: CSP error naming `accounts.google.com` | Google changed the URLs its script uses | Add the URL to the right directive in `frontend/next.config.ts` |

Google's own guide: <https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid>.
