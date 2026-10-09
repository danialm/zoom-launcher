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


ZOOM_PATTERNS = [
    r'https://[\w-]+\.zoom\.us/j/[\w?=&.-]+',
    r'https://zoom\.us/j/[\w?=&.-]+',
]

MEET_PATTERNS = [
    r'https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}',
]


def find_meeting_link(event):
    """Return a Zoom or Google Meet link for the event, preferring Zoom.

    Google Calendar often auto-attaches a Meet link even when the real
    meeting is on Zoom, so all sources are searched for Zoom first.
    """
    sources = [event.get('location', ''), event.get('description', ''), event.get('hangoutLink', '')]
    for entry in event.get('conferenceData', {}).get('entryPoints', []):
        if entry.get('entryPointType') == 'video':
            sources.append(entry.get('uri', ''))
    text = '\n'.join(s for s in sources if s)

    for pattern in ZOOM_PATTERNS + MEET_PATTERNS:
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

    # Get user's email to check their response status
    calendar_info = service.calendars().get(calendarId='primary').execute()
    user_email = calendar_info.get('id')

    now = datetime.utcnow()
    time_min = (now - timedelta(minutes=5)).isoformat() + 'Z'
    time_max = (now + timedelta(minutes=2)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        log("No events in the window (5 min ago to 2 min ahead)")
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

        # Check if user has accepted the invitation
        attendees = event.get('attendees', [])

        # Skip events with no attendees (personal events)
        if not attendees:
            log(f"Skipping (no attendees): {summary} at {start}")
            continue

        # Find user's response status
        user_response = None
        for attendee in attendees:
            if attendee.get('email', '').lower() == user_email.lower():
                user_response = attendee.get('responseStatus')
                break

        # Only proceed if user has explicitly accepted
        if user_response != 'accepted':
            status = user_response if user_response else 'no response'
            log(f"Skipping (not accepted): {summary} at {start} (status: {status})")
            continue

        # Check if already opened (event_id might have timestamp suffix)
        already_opened = any(entry.startswith(event_id) for entry in opened_meetings)
        if already_opened:
            log(f"Already opened: {summary} at {start}")
            continue

        meeting_link = find_meeting_link(event)

        if meeting_link:
            log(f"Opening meeting link for: {summary}")
            log(f"  Time: {start}")
            log(f"  Link: {meeting_link}")
            webbrowser.open(meeting_link)
            mark_meeting_opened(event_id)
        else:
            log(f"Event found but no Zoom/Meet link: {summary} at {start}")


if __name__ == '__main__':
    main()
