#!/usr/bin/env bash
# PreToolUse hook for the test-runner agent: blocks risky Bash commands.
# Exit code 2 blocks the command; Claude sees the reason on stderr.
cmd=$(jq -r '.tool_input.command // empty')

if [[ $cmd =~ (^|[[:space:]\;\&\|])(rm|curl|wget|pip|pip3)[[:space:]] ||
      $cmd =~ (poetry|uv)\ (add|remove) ||
      $cmd =~ git\ (push|commit|reset|checkout) ]]; then
  echo "test-runner only runs tests; blocked: $cmd" >&2
  exit 2
fi
exit 0
