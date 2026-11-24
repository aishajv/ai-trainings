"""Our server as an MCP *client* of Atlassian's MCP server.

get_runbook in server.py calls Atlassian's MCP tools through here, so the chain is:
  Claude Code -> oncall MCP server -> Atlassian MCP server -> Confluence

Sign in once (opens your browser, saves tokens to .atlassian_tokens.json):
  poetry run python atlassian.py login
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.client import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

ATLASSIAN_MCP = "https://mcp.atlassian.com/v2/mcp"
HERE = Path(__file__).resolve().parent
TOKENS = HERE / ".atlassian_tokens.json"  # gitignored
CALLBACK_PORT = 3119
REDIRECT = f"http://localhost:{CALLBACK_PORT}/callback"


class FileStorage(TokenStorage):
    """Keeps the OAuth client registration and tokens in one local JSON file."""

    def _read(self) -> dict:
        return json.loads(TOKENS.read_text()) if TOKENS.exists() else {}

    def _write(self, key: str, value: dict) -> None:
        data = self._read()
        data[key] = value
        TOKENS.write_text(json.dumps(data, indent=2))
        TOKENS.chmod(0o600)

    async def get_tokens(self) -> OAuthToken | None:
        raw = self._read().get("tokens")
        return OAuthToken.model_validate(raw) if raw else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._write("tokens", tokens.model_dump(mode="json", exclude_none=True))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = self._read().get("client")
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._write("client", client_info.model_dump(mode="json", exclude_none=True))


class NotSignedIn(RuntimeError):
    pass


def signed_in() -> bool:
    """True once `atlassian.py login` has saved tokens."""
    return bool(FileStorage()._read().get("tokens"))


def _provider(interactive: bool) -> OAuthClientProvider:
    async def redirect(url: str) -> None:
        if not interactive:
            raise NotSignedIn("Atlassian sign-in needed: run `poetry run python atlassian.py login` in mcp-oncall-demo/")
        print(f"Opening your browser to sign in to Atlassian:\n{url}\n")
        webbrowser.open(url)

    async def callback() -> AuthorizationCodeResult:
        result: dict = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                q = parse_qs(urlparse(self.path).query)
                result.update({k: v[0] for k, v in q.items()})
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h3>Signed in. You can close this tab.</h3>")

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        await asyncio.to_thread(thread.join)
        server.server_close()
        return AuthorizationCodeResult(code=result["code"], state=result.get("state"), iss=result.get("iss"))

    return OAuthClientProvider(
        server_url=ATLASSIAN_MCP,
        client_metadata=OAuthClientMetadata(
            client_name="oncall MCP server",
            redirect_uris=[REDIRECT],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        ),
        storage=FileStorage(),
        redirect_handler=redirect,
        callback_handler=callback,
    )


async def call(tool: str, args: dict, interactive: bool = False) -> str:
    """Call one tool on Atlassian's MCP server and return its text result."""
    http = create_mcp_http_client(auth=_provider(interactive))
    async with streamable_http_client(ATLASSIAN_MCP, http_client=http) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = "\n".join(getattr(c, "text", "") for c in result.content)
            if result.is_error:
                raise RuntimeError(f"Atlassian {tool} failed: {text[:300]}")
            return text


async def list_tools(interactive: bool = False) -> list[str]:
    http = create_mcp_http_client(auth=_provider(interactive))
    async with streamable_http_client(ATLASSIAN_MCP, http_client=http) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            return [t.name for t in (await session.list_tools()).tools]


if __name__ == "__main__":
    if sys.argv[1:] == ["login"]:
        names = asyncio.run(list_tools(interactive=True))
        print(f"Signed in. Atlassian MCP has {len(names)} tools, e.g. {', '.join(names[:4])}")
    else:
        print(__doc__)
