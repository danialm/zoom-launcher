import unittest
from datetime import datetime, timedelta, timezone

from calendar_zoom_launcher import (
    due_meetings,
    end_of_today,
    meeting_from_event,
    opened_key,
    should_sync,
    skip_reason,
)

MEET = 'https://meet.google.com/ibf-nmmd-jsd'
ZOOM = 'https://us02web.zoom.us/j/123456789?pwd=abc.1'


def at(hour, minute, second=0):
    return datetime(2026, 10, 8, hour, minute, second, tzinfo=timezone.utc)


def event(**overrides):
    base = {
        'id': 'evt1',
        'summary': 'Sean/Dan',
        'start': {'dateTime': '2026-10-08T13:00:00Z'},
        'attendees': [
            {'email': 'other@example.com', 'responseStatus': 'accepted'},
            {'email': 'me@example.com', 'self': True, 'responseStatus': 'accepted'},
        ],
        'hangoutLink': MEET,
    }
    base.update(overrides)
    return base


def meeting(start='2026-10-08T13:00:00Z', id='evt1'):
    return {'id': id, 'summary': 'Sean/Dan', 'start': start, 'link': MEET}


class ShouldSyncTest(unittest.TestCase):
    def test_syncs_without_cache(self):
        self.assertTrue(should_sync(at(13, 7), None, 15))

    def test_syncs_on_quarter_hours(self):
        for minute in (0, 15, 30, 45):
            self.assertTrue(should_sync(at(13, minute), at(13, minute) - timedelta(minutes=1), 15))

    def test_skips_between_quarter_hours_when_fresh(self):
        self.assertFalse(should_sync(at(13, 7), at(13, 0), 15))

    def test_syncs_when_stale_after_wake(self):
        self.assertTrue(should_sync(at(15, 7), at(13, 0), 15))

    def test_every_minute_interval_always_syncs(self):
        self.assertTrue(should_sync(at(13, 7), at(13, 6), 1))


class EndOfTodayTest(unittest.TestCase):
    def test_late_evening_ends_at_next_local_midnight(self):
        now = datetime(2026, 10, 8, 23, 59).astimezone()
        self.assertEqual(end_of_today(now), datetime(2026, 10, 9).astimezone())

    def test_just_after_midnight_covers_the_whole_day(self):
        now = datetime(2026, 10, 9, 0, 1).astimezone()
        self.assertEqual(end_of_today(now), datetime(2026, 10, 10).astimezone())


class MeetingFromEventTest(unittest.TestCase):
    def test_accepted_meet(self):
        self.assertEqual(meeting_from_event(event()), meeting())

    def test_prefers_zoom_over_auto_attached_meet(self):
        self.assertEqual(meeting_from_event(event(location=ZOOM))['link'], ZOOM)

    def test_not_accepted(self):
        for status in ('declined', 'tentative', 'needsAction'):
            attendees = [{'email': 'me@example.com', 'self': True, 'responseStatus': status}]
            self.assertIsNone(meeting_from_event(event(attendees=attendees)))

    def test_no_attendees(self):
        self.assertIsNone(meeting_from_event(event(attendees=[])))

    def test_all_day(self):
        self.assertIsNone(meeting_from_event(event(start={'date': '2026-10-08'})))

    def test_cancelled(self):
        self.assertIsNone(meeting_from_event(event(status='cancelled')))

    def test_no_link(self):
        self.assertIsNone(meeting_from_event(event(hangoutLink='')))


class SkipReasonTest(unittest.TestCase):
    def test_launchable(self):
        self.assertIsNone(skip_reason(event()))

    def test_reasons(self):
        declined = [{'email': 'me@example.com', 'self': True, 'responseStatus': 'declined'}]
        cases = {
            'cancelled': event(status='cancelled'),
            'all-day event': event(start={'date': '2026-10-08'}),
            'no attendees': event(attendees=[]),
            'not accepted (declined)': event(attendees=declined),
            'not accepted (not invited)': event(attendees=[{'email': 'other@example.com'}]),
            'no Zoom/Meet link': event(hangoutLink=''),
        }
        for reason, evt in cases.items():
            self.assertEqual(skip_reason(evt), reason)


class DueMeetingsTest(unittest.TestCase):
    def test_not_due_before_start(self):
        self.assertEqual(due_meetings([meeting()], at(12, 59, 59), set()), [])

    def test_due_at_start(self):
        self.assertEqual(due_meetings([meeting()], at(13, 0), set()), [meeting()])

    def test_due_within_grace_period(self):
        self.assertEqual(due_meetings([meeting()], at(13, 4, 59), set()), [meeting()])

    def test_not_due_after_grace_period(self):
        self.assertEqual(due_meetings([meeting()], at(13, 5), set()), [])

    def test_not_due_when_already_opened(self):
        self.assertEqual(due_meetings([meeting()], at(13, 0), {opened_key(meeting())}), [])

    def test_rescheduled_meeting_is_due_again(self):
        moved = meeting(start='2026-10-08T14:00:00Z')
        self.assertEqual(due_meetings([moved], at(14, 0), {opened_key(meeting())}), [moved])

    def test_simultaneous_meetings_all_due(self):
        both = [meeting(id='a'), meeting(id='b')]
        self.assertEqual(due_meetings(both, at(13, 0), set()), both)


if __name__ == '__main__':
    unittest.main()
