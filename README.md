# Google Calendar Zoom Launcher Setup

This script syncs your Google Calendar every 15 minutes and opens Zoom or Google Meet links right when your accepted meetings start.

## Prerequisites

- Python 3.10
- A Google account with Google Calendar

## Setup Instructions

### 1. Install Python (if not already installed)

This project requires Python 3.10.

```bash
# Install asdf if you don't have it
brew install asdf

# Add asdf to your shell (add to ~/.zshrc or ~/.bashrc)
echo 'source /opt/homebrew/opt/asdf/libexec/asdf.sh' >> ~/.zshrc

# Restart your shell, then install Python plugin
asdf plugin add python

# Install Python 3.10.0
asdf install python 3.10.0

# Set it as your global default (optional)
asdf global python 3.10.0
```

#### Verify Installation

```bash
python --version
# Should show Python 3.10.0
```

### 2. Install Python Dependencies

```bash
pip3 install -r requirements_calendar.txt
```

**Note for asdf users:** If you're using asdf and installed a different Python version than 3.10.0, update the Python path in `run_launcher.sh` to match your version:

```bash
# Edit line 8 in run_launcher.sh to match your Python version
exec "$HOME/.asdf/installs/python/YOUR_VERSION/bin/python3" "$SCRIPT_DIR/calendar_zoom_launcher.py"
```

### 3. Set Up Google Calendar API Credentials

#### Step 1: Enable the Google Calendar API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Click "Enable APIs and Services"
4. Search for "Google Calendar API"
5. Click "Enable"

#### Step 2: Create OAuth 2.0 Credentials

1. In the Google Cloud Console, go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" (unless you have a Google Workspace account)
   - Fill in the required fields (App name, user support email, developer email)
   - Add yourself as a test user
   - Save and continue through the scopes screen (no scopes needed at this step)
4. Back at "Create OAuth client ID":
   - Application type: "Desktop app"
   - Name: "Calendar Zoom Launcher" (or any name you prefer)
5. Click "Create"
6. Download the JSON file
7. Rename it to `credentials.json` and place it in this directory

### 4. First Run (Authorization)

Run the script manually for the first time:

```bash
./run_launcher.sh --auth
```

This will:

- Open your browser
- Ask you to authorize the application
- Save a `token.json` file for future use

Run the same command again any time the log says authorization has expired.

### 5. Set Up Automated Execution (macOS)

Run the installation script to automatically configure the launchd agent:

```bash
./install.sh
```

This script will:

- Generate the plist file with the correct paths for your system
- Copy it to `~/Library/LaunchAgents/`
- Load the service automatically

#### Useful commands:

View logs:

```bash
tail -f /tmp/calendar_zoom_launcher.log
```

View errors:

```bash
tail -f /tmp/calendar_zoom_launcher_error.log
```

Check if service is running:

```bash
launchctl list | grep calendar.zoom
```

Stop the automation:

```bash
launchctl unload ~/Library/LaunchAgents/com.calendar.zoom.launcher.plist
```

Restart after code changes:

```bash
./install.sh
```

## How It Works

launchd runs the script at the top of every minute. Each run is short-lived:

1. **Sync** (every `SYNC_INTERVAL_MINUTES`, default 15, aligned to the clock: :00, :15, :30, :45; or whenever the cache is missing or older than that, e.g. after the Mac wakes):
   fetches the rest of today's events (until local midnight) from your primary Google Calendar and saves the ones worth opening to `.events_cache.json`. An event qualifies when:
   - It has a start time (all-day events are skipped)
   - It has attendees and you have accepted it
   - It has a Zoom or Google Meet link (location, description, conferenceData, or hangout link). Zoom is preferred when both are present, since Google Calendar often auto-attaches a Meet link.
2. **Launch**: any cached meeting that has started within the last 5 minutes and hasn't been opened yet is re-checked with Google (still accepted, not cancelled or moved) and its link is opened in your default browser. If the re-check fails (e.g. offline), the cached link is opened anyway.
3. Opened meetings are tracked in `.opened_meetings` (entries older than 24 hours are removed) so nothing opens twice.

Minutes that don't sync only read the local cache, so they make no network calls.

Settings at the top of `calendar_zoom_launcher.py` (take effect on the next run, no reinstall needed):

- `SYNC_INTERVAL_MINUTES`: how often to sync (default 15; set to 1 to sync every minute)
- `LEAD_MINUTES`: open links this many minutes before the meeting starts (default 0)

### Running the tests

```bash
.venv/bin/python3 -m unittest -v
```

## Troubleshooting

### "credentials.json not found"

Make sure you've downloaded the OAuth credentials from Google Cloud Console and placed them in the correct directory.

### "Permission denied"

Make the script executable:

```bash
chmod +x calendar_zoom_launcher.py
```

### Authorization expired

The log will say `Google authorization expired`. Run `./run_launcher.sh --auth` to re-authorize.

### Meeting links not being detected

The script looks for patterns like `https://zoom.us/j/...`, `https://company.zoom.us/j/...`, or `https://meet.google.com/abc-defg-hij`. If your links have a different format, you may need to adjust the regex patterns in the script.

### Script not running automatically

Check the launchd logs:

```bash
cat /tmp/calendar_zoom_launcher.log
cat /tmp/calendar_zoom_launcher_error.log
```

**Common causes:**

1. **Python dependencies not installed**: Make sure you've run `pip3 install -r requirements_calendar.txt` with the Python installation you use (system Python, Homebrew, asdf, etc.)
2. **Permission issues**: Don't place the project in restricted folders like Desktop or Documents. Use a location like `/Users/your-username/zoom-launcher` instead
3. **Service not loaded**: Run `./install.sh` to ensure the service is properly configured and loaded

If you see "Operation not permitted" errors, try moving the project to a different location (outside Desktop/Documents) and run `./install.sh` again.
