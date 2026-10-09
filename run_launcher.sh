#!/bin/bash
# Wrapper script to run calendar_zoom_launcher.py with user's environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Prefer a project-local virtualenv; fall back to the asdf Python install
if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/calendar_zoom_launcher.py" "$@"
fi
exec "$HOME/.asdf/installs/python/3.10.0/bin/python3" "$SCRIPT_DIR/calendar_zoom_launcher.py" "$@"
