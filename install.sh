#!/usr/bin/env bash
# Installs the watcher and portal as systemd --user services, pointing at
# wherever this checkout actually lives. Re-run after moving the project.
set -euo pipefail

P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNITS="$HOME/.config/systemd/user"
PY="$P/.venv/bin/python"

[ -x "$PY" ] || { echo "No venv at $PY — run: python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f "$P/config.toml" ] || { echo "No config.toml — run: cp config.example.toml config.toml, then edit it"; exit 1; }

mkdir -p "$UNITS" "$HOME/.config/cv-router"

for svc in watcher portal; do
  sed -e "s|@WORKDIR@|$P|g" -e "s|@PYTHON@|$PY|g" \
      "$P/systemd/cv-router-$svc.service.in" > "$UNITS/cv-router-$svc.service"
done

systemctl --user daemon-reload
systemctl --user enable --now cv-router-watcher.service cv-router-portal.service
systemctl --user --no-pager status cv-router-watcher.service --lines=5 || true

PORT="$(sed -n 's/^port *= *\([0-9]*\).*/\1/p' "$P/config.toml" | head -1)"
echo
echo "Portal: http://127.0.0.1:${PORT:-8770}"
