#!/usr/bin/env python3
"""Open Zoom / Google Meet links when accepted calendar meetings start.

launchd runs this at the top of every minute. Each run:
  1. Syncs the rest of today's meetings from Google Calendar into a local cache,
     every SYNC_INTERVAL_MINUTES (on the clock) or whenever the cache is missing or stale.
  2. Opens any cached meeting that is due, after re-checking it with Google.
"""
import json
import re
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SCRIPT_DIR = Path(__file__).parent
TOKEN_PATH = SCRIPT_DIR / 'token.json'
CREDENTIALS_PATH = SCRIPT_DIR / 'credentials.json'
OPENED_MEETINGS_PATH = SCRIPT_DIR / '.opened_meetings'
CACHE_PATH = SCRIPT_DIR / '.events_cache.json'

# How often to sync with Google Calendar. Divisors of 60 keep syncs aligned to the clock (:00, :15, ...)
SYNC_INTERVAL_MINUTES = 15
# Open meetings this long after their start if they were missed (e.g. the Mac was asleep)
GRACE_PERIOD = timedelta(minutes=5)
# Open meetings this many minutes before they start
LEAD_MINUTES = 0
OPENED_RETENTION = timedelta(hours=24)

ZOOM_PATTERNS = [
    r'https://[\w-]+\.zoom\.us/j/[\w?=&.-]+',
    r'https://zoom\.us/j/[\w?=&.-]+',
]

MEET_PATTERNS = [
    r'https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}',
]


AUTH_MESSAGE = "Google authorization expired. Run `./run_launcher.sh --auth` to re-authorize."


class AuthRequired(Exception):
    pass


def log(message):
    """Print message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)


def get_calendar_service(interactive):
    # Imported lazily so minutes that only check the cache stay fast
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except RefreshError:
                pass

        if not refreshed:
            if not interactive:
                raise AuthRequired()
            if not CREDENTIALS_PATH.exists():
                log(f"Error: credentials.json not found at {CREDENTIALS_PATH}")
                log("Please follow the setup instructions in README.md")
                sys.exit(1)

            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


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


def parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def skip_reason(event):
    """Return why the event won't be opened, or None if it will.

    Only timed, non-cancelled events with attendees that the user has
    accepted and that have a Zoom/Meet link are opened.
    """
    if event.get('status') == 'cancelled':
        return "cancelled"

    if not event.get('start', {}).get('dateTime'):
        return "all-day event"

    attendees = event.get('attendees', [])
    if not attendees:
        return "no attendees"

    me = next((a for a in attendees if a.get('self')), None)
    status = me.get('responseStatus') if me else None
    if status != 'accepted':
        return f"not accepted ({status or 'not invited'})"

    if not find_meeting_link(event):
        return "no Zoom/Meet link"

    return None


def meeting_from_event(event):
    """Return a cacheable meeting dict if the event should be opened, else None."""
    if skip_reason(event):
        return None

    return {
        'id': event['id'],
        'summary': event.get('summary', 'No title'),
        'start': event['start']['dateTime'],
        'link': find_meeting_link(event),
    }


def should_sync(now, synced_at, interval_minutes=SYNC_INTERVAL_MINUTES):
    if synced_at is None or now - synced_at >= timedelta(minutes=interval_minutes):
        return True
    return now.minute % interval_minutes == 0


def opened_key(meeting):
    # Include the start time so a rescheduled meeting opens again
    return f"{meeting['id']}@{meeting['start']}"


def due_meetings(meetings, now, opened_keys):
    """Meetings that have started (minus lead time), not past the grace period, not yet opened."""
    due = []
    for meeting in meetings:
        start = parse_time(meeting['start'])
        if start - timedelta(minutes=LEAD_MINUTES) <= now < start + GRACE_PERIOD \
                and opened_key(meeting) not in opened_keys:
            due.append(meeting)
    return due


def load_cache():
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        return parse_time(cache['synced_at']), cache['meetings']
    except (FileNotFoundError, ValueError, KeyError):
        return None, []


def save_cache(now, meetings):
    tmp_path = CACHE_PATH.with_suffix('.tmp')
    with open(tmp_path, 'w') as f:
        json.dump({'synced_at': now.isoformat(), 'meetings': meetings}, f, indent=2)
    tmp_path.replace(CACHE_PATH)


def load_opened_meetings():
    """Return {key: opened_at} from the tracking file, dropping entries older than 24 hours."""
    if not OPENED_MEETINGS_PATH.exists():
        return {}

    now = datetime.now(timezone.utc)
    opened = {}
    with open(OPENED_MEETINGS_PATH) as f:
        for line in f:
            key, _, timestamp = line.strip().partition('|')
            try:
                opened_at = parse_time(timestamp)
            except ValueError:
                continue
            if opened_at.tzinfo is None:
                opened_at = opened_at.astimezone(timezone.utc)
            if now - opened_at < OPENED_RETENTION:
                opened[key] = opened_at
    return opened


def save_opened_meetings(opened):
    with open(OPENED_MEETINGS_PATH, 'w') as f:
        for key, opened_at in opened.items():
            f.write(f"{key}|{opened_at.isoformat()}\n")


def end_of_today(now):
    """Local midnight at the end of the day containing `now`."""
    local = now.astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def sync(service, now):
    events_result = service.events().list(
        calendarId='primary',
        timeMin=(now - GRACE_PERIOD).isoformat(),
        timeMax=end_of_today(now).isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    meetings = [m for m in map(meeting_from_event, events) if m]
    save_cache(now, meetings)

    log(f"Synced: {len(events)} event(s) left today, {len(meetings)} launchable")
    for event in events:
        start = event.get('start', {})
        when = parse_time(start['dateTime']).astimezone().strftime('%H:%M') if 'dateTime' in start \
            else start.get('date', '?')
        reason = skip_reason(event)
        status = f"skip: {reason}" if reason else "launch"
        log(f"  {when}  {event.get('summary', 'No title')}  [{status}]")
    return meetings


def recheck(service, meeting, now):
    """Fetch the event again; return the fresh meeting if it is still due, else None."""
    event = service.events().get(calendarId='primary', eventId=meeting['id']).execute()
    fresh = meeting_from_event(event)
    if fresh and due_meetings([fresh], now, set()):
        return fresh
    return None


def main():
    interactive = sys.stdin.isatty()

    if '--auth' in sys.argv[1:]:
        get_calendar_service(interactive=True)
        log("Authorized. Calendar access is set up.")
        return

    now = datetime.now(timezone.utc)
    synced_at, meetings = load_cache()
    service = None

    def get_service():
        nonlocal service
        if service is None:
            service = get_calendar_service(interactive)
        return service

    if should_sync(now, synced_at):
        try:
            meetings = sync(get_service(), now)
        except AuthRequired:
            log(f"Sync failed, using cached meetings: {AUTH_MESSAGE}")
        except Exception as e:
            log(f"Sync failed, using cached meetings: {e}")

    opened = load_opened_meetings()
    for meeting in due_meetings(meetings, now, opened.keys()):
        try:
            fresh = recheck(get_service(), meeting, now)
            if not fresh:
                log(f"Skipping (changed since sync): {meeting['summary']}")
                opened[opened_key(meeting)] = now
                continue
            meeting = fresh
        except AuthRequired:
            log(f"Re-check failed, opening cached link anyway: {AUTH_MESSAGE}")
        except Exception as e:
            log(f"Re-check failed, opening cached link anyway: {e}")

        log(f"Opening meeting link for: {meeting['summary']}")
        log(f"  Time: {meeting['start']}")
        log(f"  Link: {meeting['link']}")
        webbrowser.open(meeting['link'])
        opened[opened_key(meeting)] = now

    save_opened_meetings(opened)


if __name__ == '__main__':
    main()
