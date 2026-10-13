// Sits between Claude Code and an MCP server and logs every message.
// Used in .mcp.json, e.g. "command": "node", "args": ["mcp-spy.mjs", "npx", "@playwright/mcp@latest"]
// Watch it: tail -f mcp-wire.log

import { spawn } from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { createInterface } from 'node:readline';

const LOG = new URL('./mcp-wire.log', import.meta.url);
const [command, ...args] = process.argv.slice(2);
const server = spawn(command, args, { stdio: ['pipe', 'pipe', 'inherit'] });
// Several servers can share one log: label each message with its package name
const name = (args.filter((arg) => !arg.startsWith('-')).pop() ?? command).replace(/@latest$/, '');

// Page snapshots can be thousands of lines long; keep the log readable
function shorten(key, value) {
  if (typeof value === 'string' && value.length > 1500) {
    return value.slice(0, 1500) + ` … [${value.length - 1500} more characters]`;
  }
  return value;
}

function log(direction, line) {
  let body = line;
  let what = 'not JSON';
  try {
    const message = JSON.parse(line);
    what = message.method ?? (message.error ? 'error' : 'result');
    body = JSON.stringify(message, shorten, 2);
  } catch {}
  const time = new Date().toTimeString().slice(0, 8);
  appendFileSync(LOG, `──── ${time}  ${name}  ${direction}  ${what}\n${body}\n\n`);
}

// Over stdio, each MCP message is one line of JSON: pass it on, log a copy
function pipe(from, to, direction) {
  createInterface({ input: from, crlfDelay: Infinity }).on('line', (line) => {
    log(direction, line);
    to.write(line + '\n');
  });
}

pipe(process.stdin, server.stdin, 'client → server');
pipe(server.stdout, process.stdout, 'server → client');
process.stdin.on('end', () => server.stdin.end());
server.on('exit', (code) => process.exit(code ?? 0));
