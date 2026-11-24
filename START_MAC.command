#!/bin/sh
set -eu
cd "$(dirname "$0")"
PY=""
for candidate in "$PWD/.venv/bin/python" /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,10))' >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  /usr/bin/osascript -e 'display alert "Use the Mac package" message "Extract Reunite_Mac.zip and double-click Reunite.app. That package includes Python and needs no Terminal commands."'
  exit 1
fi
exec "$PY" desktop_launcher.py
