#!/usr/bin/env python3
import re
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SCRIPT_DIR = Path(__file__).parent
TOKEN_PATH = SCRIPT_DIR / 'token.json'
CREDENTIALS_PATH = SCRIPT_DIR / 'credentials.json'
OPENED_MEETINGS_PATH = SCRIPT_DIR / '.opened_meetings'


def log(message):
    """Print message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def get_calendar_service():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                log(f"Error: credentials.json not found at {CREDENTIALS_PATH}")
                log("Please follow the setup instructions in SETUP.md")
                exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


def extract_zoom_link(text):
    if not text:
        return None

    zoom_patterns = [
        r'https://[\w-]+\.zoom\.us/j/[\w?=&-]+',
        r'https://zoom\.us/j/[\w?=&-]+',
    ]

    for pattern in zoom_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


def load_opened_meetings():
    if not OPENED_MEETINGS_PATH.exists():
        return set()

    with open(OPENED_MEETINGS_PATH, 'r') as f:
        return set(line.strip() for line in f if line.strip())


def mark_meeting_opened(event_id):
    opened = load_opened_meetings()
    # Store with timestamp
    timestamp = datetime.now().isoformat()
    opened.add(f"{event_id}|{timestamp}")

    with open(OPENED_MEETINGS_PATH, 'w') as f:
        for meeting_id in opened:
            f.write(f"{meeting_id}\n")


def cleanup_old_meetings():
    """Remove meeting entries older than 24 hours"""
    if not OPENED_MEETINGS_PATH.exists():
        return

    opened = load_opened_meetings()
    now = datetime.now()
    cleaned = set()

    for entry in opened:
        # Parse entry - format is "event_id|timestamp" or just "event_id" (old format)
        if '|' in entry:
            event_id, timestamp_str = entry.split('|', 1)
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                # Keep entries less than 24 hours old
                if (now - timestamp).total_seconds() < 86400:  # 24 hours
                    cleaned.add(entry)
            except (ValueError, AttributeError):
                # If timestamp parsing fails, keep the entry
                cleaned.add(entry)
        else:
            # Old format without timestamp - keep it for now
            cleaned.add(entry)

    with open(OPENED_MEETINGS_PATH, 'w') as f:
        for meeting_id in cleaned:
            f.write(f"{meeting_id}\n")


def main():
    cleanup_old_meetings()

    service = get_calendar_service()

    now = datetime.utcnow()
    time_min = (now - timedelta(minutes=5)).isoformat() + 'Z'
    time_max = (now + timedelta(minutes=5)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        log("No events in the window (5 min ago to 5 min ahead)")
        return

    opened_meetings = load_opened_meetings()

    for event in events:
        event_id = event['id']
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No title')

        # Skip events that started more than 5 minutes ago
        if 'dateTime' in event['start']:
            try:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                now_aware = datetime.now(timezone.utc)
                five_min_ago = now_aware - timedelta(minutes=5)
                if start_time < five_min_ago:
                    log(f"Skipping (started too long ago): {summary} at {start}")
                    continue
            except (ValueError, AttributeError):
                pass  # If parsing fails, continue with the event

        # Check if already opened (event_id might have timestamp suffix)
        already_opened = any(entry.startswith(event_id) for entry in opened_meetings)
        if already_opened:
            log(f"Already opened: {summary} at {start}")
            continue

        zoom_link = None

        if 'location' in event:
            zoom_link = extract_zoom_link(event['location'])

        if not zoom_link and 'description' in event:
            zoom_link = extract_zoom_link(event['description'])

        if not zoom_link and 'hangoutLink' in event:
            link = event['hangoutLink']
            if 'zoom' in link.lower():
                zoom_link = link

        # Check conferenceData for Zoom meetings added via Google Calendar integration
        if not zoom_link and 'conferenceData' in event:
            conference_data = event['conferenceData']
            if 'entryPoints' in conference_data:
                for entry in conference_data['entryPoints']:
                    if entry.get('entryPointType') == 'video':
                        uri = entry.get('uri', '')
                        if 'zoom' in uri.lower():
                            zoom_link = uri
                            break

        if zoom_link:
            log(f"Opening Zoom link for: {summary}")
            log(f"  Time: {start}")
            log(f"  Link: {zoom_link}")
            webbrowser.open(zoom_link)
            mark_meeting_opened(event_id)
        else:
            log(f"Event found but no Zoom link: {summary} at {start}")


if __name__ == '__main__':
    main()
