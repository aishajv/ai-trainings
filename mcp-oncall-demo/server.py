"""On-call MCP server for stillroom.

Run it:   poetry run python server.py
Watch it: the terminal it runs in, or `tail -f oncall.log`

Every tool call is logged in layers, so the demo shows the whole chain:
  ▶ TOOL CALL   what Claude asked for (tool + arguments)
    → UPSTREAM  what our server asked the real system (Vercel, Atlassian MCP, Slack)
  ◀ RESULT      what went back to Claude (size + preview + time)

See README.md for the tools, setup and the loop-then-graph demo.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError  # message is shown to Claude so it can self-correct

import atlassian  # our server is also an MCP client of Atlassian's MCP server

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

# ---------------------------------------------------------------- logging
log = logging.getLogger("oncall")
log.setLevel(logging.INFO)
log.propagate = False  # the MCP SDK installs its own root handler; avoid double lines
logging.getLogger("httpx").setLevel(logging.WARNING)  # our UPSTREAM line replaces httpx's own
_fmt = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
for handler in (logging.StreamHandler(), logging.FileHandler(HERE / "oncall.log")):
    handler.setFormatter(_fmt)
    log.addHandler(handler)

CYAN, YELLOW, GREEN, RED, DIM, RESET = "\033[36m", "\033[33m", "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def _preview(value: Any, limit: int = 300) -> str:
    text = json.dumps(value, default=str) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + f"… ({len(text)} chars)"


def logged(fn):
    """Log every call Claude makes to a tool: arguments in, result out, time taken."""

    def _start(args, kwargs):
        bound = inspect.signature(fn).bind(*args, **kwargs)
        log.info(f"{CYAN}▶ TOOL CALL  {fn.__name__}({_preview(dict(bound.arguments))}){RESET}")
        return time.perf_counter()

    def _end(start, result):
        ms = (time.perf_counter() - start) * 1000
        log.info(f"{GREEN}◀ RESULT     {fn.__name__} in {ms:.0f} ms: {_preview(result)}{RESET}")

    def _fail(exc):
        log.info(f"{RED}✖ ERROR      {fn.__name__}: {exc}{RESET}")

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            start = _start(args, kwargs)
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                _fail(exc)
                raise
            _end(start, result)
            return result

        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = _start(args, kwargs)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            _fail(exc)
            raise
        _end(start, result)
        return result

    return wrapper


def _log_step(what: str, outcome: str) -> None:
    """One UPSTREAM line for calls that don't go through httpx (CLI, other MCP servers)."""
    log.info(f"{YELLOW}  → UPSTREAM  {what}  ←  {outcome}{RESET}")


def _log_upstream(response: httpx.Response) -> None:
    req = response.request
    path = req.url.copy_remove_param("teamId").raw_path.decode()  # never log tokens: they live in headers
    log.info(f"{YELLOW}  → UPSTREAM  {req.method} {req.url.host}{path}  ←  {response.status_code}{RESET}")


# ---------------------------------------------------------------- data sources
CATALOG = yaml.safe_load((HERE / "services.yaml").read_text())

VERCEL = httpx.Client(
    base_url="https://api.vercel.com",
    headers={"Authorization": f"Bearer {os.environ.get('VERCEL_TOKEN', '')}"},
    timeout=15,
    event_hooks={"response": [_log_upstream]},
)


def _service(service: str) -> dict:
    if service not in CATALOG:
        raise ToolError(f"unknown service '{service}'. Known services: {', '.join(CATALOG)}")
    return CATALOG[service]


# ---------------------------------------------------------------- the MCP server
mcp = MCPServer(
    "oncall",
    instructions=(
        "On-call tools for production services. Start with get_service_owner, "
        "then get_errors and get_recent_deploys to see what broke and what changed, "
        "then get_runbook for the fix. All tools are read-only except post_to_slack, "
        "which must only be called after a person has approved the message."
    ),
)


@mcp.tool()
@logged
def get_service_owner(service: str) -> dict:
    """Who owns a service, how to reach them, who to escalate to, and where it runs.

    Use this first in any incident. `service` is the short name, e.g. "stillroom".
    """
    entry = _service(service)
    return {k: v for k, v in entry.items() if k not in ("vercel", "confluence")}


@mcp.tool()
@logged
def get_recent_deploys(service: str, limit: int = 5) -> list[dict]:
    """The most recent deploys of a service, newest first.

    Each deploy has its time, environment (production or preview), state, URL and the
    git commit behind it when the project is linked to git. Use it to answer
    "what changed just before the errors started?".
    """
    cfg = _service(service)["vercel"]
    response = VERCEL.get(
        "/v6/deployments",
        params={"projectId": cfg["project"], "slug": cfg["team"], "limit": min(limit, 20)},
    )
    if response.status_code in (401, 403):
        raise ToolError("Vercel rejected the token. Check VERCEL_TOKEN in mcp-oncall-demo/.env.")
    response.raise_for_status()

    deploys = []
    for d in response.json()["deployments"]:
        meta = d.get("meta") or {}
        deploys.append(
            {
                "id": d["uid"],
                "created": datetime.fromtimestamp(d["created"] / 1000, UTC).isoformat(timespec="seconds"),
                "environment": d.get("target") or "preview",
                "state": d.get("state") or d.get("readyState"),
                "url": "https://" + d["url"],
                "by": (d.get("creator") or {}).get("username"),
                "commit": (meta.get("githubCommitSha") or "")[:7] or None,
                "commit_message": meta.get("githubCommitMessage"),
            }
        )
    return deploys


@mcp.tool()
@logged
def get_errors(service: str, since_minutes: int = 10, environment: str = "all") -> dict:
    """Errors the service logged in the last N minutes, grouped by reason.

    Reads the service's runtime logs on Vercel. `environment` is "production",
    "preview" or "all". Returns a verdict ("healthy" or "errors"), call counts,
    and for each error reason: count, HTTP status, first and last time seen,
    which deployments it came from, and a sample message.
    """
    cfg = _service(service)["vercel"]
    cmd = ["vercel", "logs", "--project", cfg["project"], "--scope", cfg["team"],
           "--since", f"{since_minutes}m", "--json", "-n", "1000"]
    if environment in ("production", "preview"):
        cmd += ["--environment", environment]
    # Uses the Vercel CLI login on this machine; runs outside any project folder on purpose.
    env = {k: v for k, v in os.environ.items() if k != "VERCEL_TOKEN"}  # let the CLI use its own login
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd="/tmp", env=env)
    _log_step(f"vercel logs --project {cfg['project']} --since {since_minutes}m --environment {environment}",
              f"exit {proc.returncode}, {len(proc.stdout.splitlines())} lines")
    if proc.returncode != 0:
        raise ToolError(f"vercel logs failed: {proc.stderr.strip()[-300:]}")

    ok = 0
    reasons: dict[str, dict] = {}
    other_5xx = 0
    for line in proc.stdout.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        when = datetime.fromtimestamp(entry["timestamp"] / 1000, UTC).isoformat(timespec="seconds")
        try:
            event = json.loads(entry.get("message") or "")
        except (json.JSONDecodeError, TypeError):
            event = {}
        if not isinstance(event, dict):
            event = {}
        if event.get("event") == "youtube_ok":
            ok += 1
        elif event.get("event") == "youtube_error":
            r = reasons.setdefault(event.get("reason", "unknown"), {
                "count": 0, "status": event.get("status"), "first_seen": when, "last_seen": when,
                "environments": set(), "deployments": set(), "sample_message": event.get("message"),
            })
            r["count"] += 1
            r["first_seen"] = min(r["first_seen"], when)
            r["last_seen"] = max(r["last_seen"], when)
            r["environments"].add(entry.get("environment"))
            r["deployments"].add(entry.get("domain") or entry.get("deploymentId"))
        elif (entry.get("responseStatusCode") or 0) >= 500:
            other_5xx += 1

    for r in reasons.values():
        r["environments"] = sorted(x for x in r["environments"] if x)
        r["deployments"] = sorted(x for x in r["deployments"] if x)
    errors = sum(r["count"] for r in reasons.values()) + other_5xx
    return {
        "service": service,
        "window": f"last {since_minutes} min, {environment}",
        "verdict": "errors" if errors else "healthy",
        "youtube_calls_ok": ok,
        "errors_total": errors,
        "errors_by_reason": reasons,
        "other_5xx": other_5xx,
    }


async def _atlassian(tool: str, args: dict) -> str:
    """Call Atlassian's MCP server; turn its errors into a readable message for Claude."""
    try:
        return await atlassian.call(tool, args)
    except Exception as exc:  # the MCP client wraps failures in exception groups
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        _log_step(f"MCP atlassian.{tool}", f"failed: {exc}")
        raise ToolError(f"Atlassian MCP call {tool} failed: {exc}") from exc


def _sections(markdown: str) -> dict[str, str]:
    """Split a page into its '## heading' sections."""
    out: dict[str, str] = {}
    current = None
    for line in markdown.splitlines():
        m = re.match(r"^#{1,3}\s+(.*)", line)
        if m:
            current = m.group(1).strip().lower()
            out[current] = ""
        elif current:
            out[current] += line + "\n"
    return out


@mcp.tool()
@logged
async def get_runbook(service: str, symptom: str) -> str:
    """The runbook steps for one symptom, from the service's Confluence runbook page.

    Symptoms on the stillroom page: "bad deploy", "key", "quota", "network",
    "when to escalate". Reads Confluence through Atlassian's MCP server.
    """
    cfg = _service(service)["confluence"]
    if not atlassian.signed_in():
        raise ToolError("Atlassian sign-in needed: run `poetry run python atlassian.py login` in mcp-oncall-demo/.")
    cql = f'title = "{cfg["page_title"]}" AND space = "{cfg["space"]}" AND type = page'
    found = await _atlassian("searchConfluenceUsingCql", {"cloudId": cfg["cloud_id"], "cql": cql})
    ids = re.findall(r'"id"\s*:\s*"?(\d+)"?', found)
    _log_step(f"MCP atlassian.searchConfluenceUsingCql({cql})", f"{len(ids)} ids")
    if not ids:
        raise ToolError(f"No Confluence page titled '{cfg['page_title']}' in space {cfg['space']}.")

    page = await _atlassian("getConfluencePage",
                            {"cloudId": cfg["cloud_id"], "pageId": ids[0], "contentFormat": "markdown"})
    _log_step(f"MCP atlassian.getConfluencePage({ids[0]})", f"{len(page)} chars")
    try:  # the page may come back as JSON with the body inside
        data = json.loads(page)
        body = (data.get("body") if isinstance(data, dict) else None) or page
        if isinstance(body, dict):
            body = json.dumps(body)
    except json.JSONDecodeError:
        body = page

    sections = _sections(body)
    want = symptom.strip().lower()
    for heading, text in sections.items():
        if heading == want or heading.startswith(want) or want in heading:
            return f"## {heading}\n{text.strip()}"
    raise ToolError(f"No runbook section for '{symptom}'. Sections: {', '.join(sections)}")


@mcp.tool()
@logged
def post_to_slack(service: str, text: str) -> dict:
    """Post an incident update to the service's on-call Slack channel.

    The only tool that changes anything. Call it ONLY after a person has read the
    message and said to post it.
    """
    channel = _service(service).get("slack_channel", "#oncall")
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise ToolError("SLACK_WEBHOOK_URL is not set in mcp-oncall-demo/.env.")
    response = httpx.post(url, json={"text": text}, timeout=10)
    _log_step(f"POST hooks.slack.com (webhook for {channel})", str(response.status_code))
    if response.status_code != 200:
        raise ToolError(f"Slack rejected the message: {response.status_code} {response.text[:200]}")
    return {"posted": True, "channel": channel, "chars": len(text)}


if __name__ == "__main__":
    port = int(os.environ.get("ONCALL_PORT", "8900"))
    log.info(f"{DIM}oncall MCP server on http://127.0.0.1:{port}/mcp  ·  log file: {HERE / 'oncall.log'}{RESET}")
    mcp.run("streamable-http", port=port)
