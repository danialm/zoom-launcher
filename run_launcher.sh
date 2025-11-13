#!/bin/bash
# Wrapper script to run calendar_zoom_launcher.py with user's environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source the user's profile to get their PATH (including asdf, pyenv, etc.)
# Redirect stderr to suppress shell-specific warnings
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bash_profile" ]; then
    source "$HOME/.bash_profile" 2>/dev/null || true
elif [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" 2>/dev/null || true
fi

# Run the Python script
exec python3 "$SCRIPT_DIR/calendar_zoom_launcher.py" 2>&1
