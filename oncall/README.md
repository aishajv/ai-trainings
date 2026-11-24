# On-call MCP server

An MCP server that gives Claude Code the facts you need when production breaks, for one real
service: **stillroom**, a Vercel site that plays calm YouTube pieces. Claude asks; the server fetches
from the real systems and hands back short, shaped answers. Every call is logged so the audience can
watch it happen.

```
Claude Code ──▶ oncall MCP server ──▶ services.yaml          (owner)
                (server.py, HTTP)  ──▶ Vercel API / logs      (deploys, errors)
                                   ──▶ Atlassian MCP server   (runbook in Confluence)
                                   ──▶ Slack webhook          (post, after approval)
```

## The tools

| Tool | Answers | Reads from |
|---|---|---|
| `get_service_owner` | Who owns it, how to reach them | `services.yaml` |
| `get_recent_deploys` | What shipped, when, where | Vercel API `/v6/deployments` |
| `get_errors` | What is failing right now, grouped by reason | Vercel runtime logs (`vercel logs`) |
| `get_runbook` | The fix for one symptom | Confluence, through Atlassian's MCP server |
| `post_to_slack` | Posts the approved diagnosis | Slack incoming webhook. The only tool that changes anything |

`get_runbook` makes this server an MCP **client** too: it calls Atlassian's MCP server
(`atlassian.py`), so one MCP server chains into another.

## Files

| Path | What it is |
|---|---|
| `server.py` | The MCP server: tools, call logging, HTTP entry point |
| `atlassian.py` | MCP client for Atlassian's MCP server, with OAuth sign-in |
| `services.yaml` | Service catalog: owner, Slack, Vercel project, Confluence page |
| `runbooks/stillroom-runbook.md` | Source copy of the Confluence runbook |
| `stillroom/api/youtube.js` | The function added to stillroom: holds the YouTube key server-side and logs every call |
| `.env` | Secrets, gitignored: `VERCEL_TOKEN`, `SLACK_WEBHOOK_URL` |

## Run it

Requires Python 3.12, Poetry and the Vercel CLI signed in (`vercel login`).

```bash
cd oncall
poetry install
poetry run python atlassian.py login   # once: opens the browser to sign in to Atlassian
poetry run python server.py            # leave this terminal open: it is the live call log
```

The server listens on `http://127.0.0.1:8900/mcp`; `.mcp.json` at the repo root registers it as
`oncall`. Restart Claude Code (or `/mcp` → reconnect) after starting it.

Secrets go in `oncall/.env` without pasting them anywhere:

```bash
bash -c 'read -s -p "Vercel token: " t; echo; echo "VERCEL_TOKEN=$t" >> .env'
bash -c 'read -s -p "Slack webhook URL: " u; echo; echo "SLACK_WEBHOOK_URL=$u" >> .env'
```

## Reading the log

```
18:57:10  ▶ TOOL CALL  get_errors({"service": "stillroom", "since_minutes": 2})     what Claude asked
18:57:11    → UPSTREAM  vercel logs --project still-room-fre --since 2m  ←  exit 0  what we asked Vercel
18:57:11  ◀ RESULT     get_errors in 812 ms: {"verdict": "errors", ...}            what went back
```

## The demo: loop, then graph

1. Start the loop while stillroom is healthy:

   ```
   /loop 1m Check stillroom for errors in the last 2 minutes.

   If it's healthy: reply only "✓ check N: healthy".

   If there are errors: stop this loop and debug it with a dynamic
   workflow that follows this graph, naming each step as you go:
     1. GATHER: owner, recent deploys, errors from the last 15 minutes,
        and the runbook section for the error.
     2. DRAFT: what broke, where, since when, likely cause, runbook fix.
     3. VERIFY: check every claim against what you gathered.
        If one isn't supported, go back to DRAFT (max 2 times).
     4. APPROVE: show me the diagnosis and wait for "approve".
     5. POST: send it to the on-call Slack channel.

   Never change code, settings or deployments. Stop after 30 checks.
   ```

2. Break a Preview: `vercel env rm YOUTUBE_API_KEY preview`, redeploy to Preview, open a room on it.
3. The next check sees `keyMissing`, stops the loop, and runs the five steps. Say "approve" to post.
4. Fix it: `vercel env add YOUTUBE_API_KEY preview`, redeploy.

**Loop** = the same step on a timer until a stop rule. **Graph** = different steps in a fixed order,
with a step back (verify → draft) and a pause for a person (approve).

## Way forward in your stack

The tools stay the same; only the sources change.

| Tool | Here | In an AWS / .NET / PHP stack |
|---|---|---|
| `get_service_owner` | `services.yaml` | CODEOWNERS, Jira component lead |
| `get_recent_deploys` | Vercel API | CodePipeline or GitHub Actions |
| `get_errors` | Vercel logs | CloudWatch Logs Insights, read-only IAM role |
| `get_runbook` | Confluence via Atlassian MCP | Same |
| `post_to_slack` | Slack webhook | Same, a test channel first |
