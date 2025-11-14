#!/bin/bash
# Wrapper script to run calendar_zoom_launcher.py with user's environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Try to find python3 in common locations
PYTHON=""

# Check common Python manager locations first
if [ -f "$HOME/.asdf/shims/python3" ]; then
    PYTHON="$HOME/.asdf/shims/python3"
elif command -v pyenv &> /dev/null && [ -f "$(pyenv which python3 2>/dev/null)" ]; then
    PYTHON="$(pyenv which python3)"
elif [ -f "/opt/homebrew/bin/python3" ]; then
    PYTHON="/opt/homebrew/bin/python3"
elif [ -f "/usr/local/bin/python3" ]; then
    PYTHON="/usr/local/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON="$(command -v python3)"
else
    PYTHON="/usr/bin/python3"
fi

# Run the Python script
exec "$PYTHON" "$SCRIPT_DIR/calendar_zoom_launcher.py"
