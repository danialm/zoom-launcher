#!/bin/bash
# Wrapper script to run calendar_zoom_launcher.py with user's environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Use the specific Python version with Google Calendar dependencies installed
exec "$HOME/.asdf/installs/python/3.10.0/bin/python3" "$SCRIPT_DIR/calendar_zoom_launcher.py"
