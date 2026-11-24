# stillroom runbook

> Source copy of the Confluence page "stillroom runbook" (space MFS). `get_runbook` reads the
> Confluence page, not this file; keep the two in sync.

**Service:** stillroom, a site that plays long, calm YouTube pieces by room (rainy café, 2 a.m., deep space…)

**Live:** https://still-room-fre.vercel.app

**Hosting:** Vercel project `still-room-fre` (team `solo-tam`)

**Owner:** Aisha (Slack @aisha) · **Escalation:** team lead · **Channel:** #oncall

**Where to look:** Vercel → Logs (filter `/api/youtube`) · Vercel → Deployments (what shipped, when)

**How it works:** the browser asks our own function `/api/youtube`. That function calls the YouTube
Data API v3 with the key stored in Vercel as the environment variable `YOUTUBE_API_KEY`. The key never
reaches the browser. Every call writes one JSON log line: `youtube_ok` when it works, `youtube_error`
with a `reason` when it fails.

**First five minutes, every time**

1. Check the errors: which `reason`, how many, and when did they start (`first_seen`)? Production, Preview, or both?
2. Open Vercel Deployments: did anything deploy shortly before `first_seen`?
3. Pick the matching section below. If errors started right after a deploy, start with **bad deploy**.
4. Post a one-line status in #oncall: what is broken, since when, what you are doing.

---

## bad deploy

**Symptom:** errors start within minutes of a deploy and come only from the new deployment. A deploy
includes its settings: an environment variable removed or changed before the deploy breaks it just
like bad code.

**Check**

- Do the errors come from one deployment only? Compare `deployments` in the error summary with the newest deploy.
- Did the previous deployment work? If yes, the change is in this deploy: code or settings.
- Reason `keyMissing` means the deploy was built without `YOUTUBE_API_KEY`. Go to **key**.

**Mitigate: roll back first, fix later**

```
vercel rollback                      # production: back to the previous deployment
# Preview: don't promote it; fix and redeploy instead
```

Then open `?room=books` on the affected URL and confirm videos load and errors stop.

---

## key

**Symptom:** every search fails. Reasons: `keyMissing` (no key in this deployment), `keyInvalid` or
`forbidden` (YouTube rejected the key).

**Check**

- `vercel env ls`: is `YOUTUBE_API_KEY` set for the affected environment (Production or Preview)?
- Settings only apply to new deploys. A key added or changed after the last deploy needs a redeploy.
- Google Cloud Console → Credentials → the stillroom key:
  - Was it deleted or regenerated?
  - **Application restrictions** must be **None**: our server calls YouTube, not a browser.
  - **API restrictions:** YouTube Data API v3 must be allowed.

**Mitigate:** put the key back (`vercel env add YOUTUBE_API_KEY <environment>`), then redeploy. Never
paste the key into Slack, tickets or chat.

---

## quota

**Symptom:** reason `quotaExceeded` or `dailyLimitExceeded`. Usually late in the day (Pacific time), not tied to a deploy.

**Check**

- Google Cloud Console → YouTube Data API v3 → Quotas: is usage at 10,000 units today?
- Each room or search costs about 100 units, so the free tier covers about 100 searches a day.

**Mitigate**

- Quota resets at midnight Pacific. If that is soon, post the status and wait.
- Otherwise switch to a backup key from a separate Google Cloud project and redeploy.
- Do not roll back: a deploy did not cause this.

---

## network

**Symptom:** reason `network`: our function could not reach YouTube.

**Check:** is YouTube or Google APIs down? Do the errors come in a short burst?

**Mitigate:** usually nothing to do on our side. Post the status and keep watching until errors fall.

---

## when to escalate

- Users cannot play anything for more than 30 minutes and no section above helps.
- You need access you do not have (Google Cloud project, Vercel team).
- You are about to do something you cannot undo, like deleting a key or a deployment.

## after the incident

Write three lines in the incident log: what broke, what you did, what would have caught it sooner.
