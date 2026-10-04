#!/usr/bin/env bash
# PreToolUse hook for the ticket-implementer agent: git hooks (tests, lint) must run.
# Exit code 2 blocks the command; Claude sees the reason on stderr.
cmd=$(jq -r '.tool_input.command // empty')

if [[ $cmd =~ --no-verify || $cmd =~ git\ commit.*[[:space:]]-[a-zA-Z]*n ]]; then
  echo "git hooks must run; fix the failing checks instead of skipping them: $cmd" >&2
  exit 2
fi
exit 0
