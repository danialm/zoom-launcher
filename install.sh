#!/bin/bash
# Installation script for calendar zoom launcher

set -e

# Get the absolute path to the project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing Calendar Zoom Launcher..."
echo "Project directory: $PROJECT_DIR"

# Generate the plist file from template
PLIST_FILE="$PROJECT_DIR/com.calendar.zoom.launcher.plist"
sed "s|PROJECT_DIR|$PROJECT_DIR|g" "$PROJECT_DIR/com.calendar.zoom.launcher.plist.template" > "$PLIST_FILE"

echo "Generated plist file: $PLIST_FILE"

# Copy to LaunchAgents
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
cp "$PLIST_FILE" "$LAUNCH_AGENTS_DIR/"

echo "Copied plist to $LAUNCH_AGENTS_DIR"

# Unload if already loaded (ignore errors)
launchctl unload "$LAUNCH_AGENTS_DIR/com.calendar.zoom.launcher.plist" 2>/dev/null || true

# Load the service
launchctl load "$LAUNCH_AGENTS_DIR/com.calendar.zoom.launcher.plist"

echo ""
echo "✓ Installation complete!"
echo ""
echo "The service will run every 2 minutes and check for meetings"
echo "starting in the next 5 minutes (or that started in the last 5 minutes)."
echo ""
echo "Useful commands:"
echo "  View logs:      tail -f /tmp/calendar_zoom_launcher.log"
echo "  View errors:    tail -f /tmp/calendar_zoom_launcher_error.log"
echo "  Check status:   launchctl list | grep calendar.zoom"
echo "  Uninstall:      launchctl unload ~/Library/LaunchAgents/com.calendar.zoom.launcher.plist"
echo ""
