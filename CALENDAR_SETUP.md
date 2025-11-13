# Google Calendar Zoom Launcher Setup

This script automatically checks your Google Calendar every few minutes and opens Zoom links for meetings starting in the next 5 minutes.

## Prerequisites

- Python 3.7 or higher
- A Google account with Google Calendar

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip3 install -r requirements_calendar.txt
```

### 2. Set Up Google Calendar API Credentials

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

### 3. First Run (Authorization)

Run the script manually for the first time:

```bash
python3 calendar_zoom_launcher.py
```

This will:

- Open your browser
- Ask you to authorize the application
- Save a `token.json` file for future use

Once authorized, the script will check for upcoming meetings and open any Zoom links found.

### 4. Set Up Automated Execution (macOS)

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

1. Every 2 minutes, the script checks your primary Google Calendar
2. It looks for events that:
   - Started within the last 5 minutes, OR
   - Will start in the next 5 minutes
3. If an event has a Zoom link (in location, description, conferenceData, or hangout link), it opens it in your default browser
4. It tracks which meetings it has already opened to avoid duplicates
5. The tracking data is automatically cleaned up (entries older than 24 hours are removed)

## Troubleshooting

### "credentials.json not found"

Make sure you've downloaded the OAuth credentials from Google Cloud Console and placed them in the correct directory.

### "Permission denied"

Make the script executable:

```bash
chmod +x calendar_zoom_launcher.py
```

### Authorization expired

Delete `token.json` and run the script manually again to re-authorize.

### Zoom links not being detected

The script looks for patterns like `https://zoom.us/j/...` or `https://company.zoom.us/j/...`. If your Zoom links have a different format, you may need to adjust the regex patterns in the script.

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
