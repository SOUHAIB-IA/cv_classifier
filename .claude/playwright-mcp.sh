#!/usr/bin/env bash
# Launch the Playwright MCP server with a Node it can actually run on.
#
# @playwright/mcp needs Node 20 or newer. The Node on this machine's PATH is
# Ubuntu's 18.19.1, so the server started, printed "Please update your version
# of Node.js" and timed out the handshake. Node 22 is installed through nvm but
# a server process does not inherit an interactive shell, so nvm is sourced
# here instead of being assumed.
#
# Sourcing by version rather than by path on purpose: an absolute path to
# v22.14.0 would break the day that version is removed, silently, months later.
set -euo pipefail
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# stdout belongs to the JSON-RPC stream, so nothing here may write to it.
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1 || true
exec npx -y @playwright/mcp@latest "$@"
