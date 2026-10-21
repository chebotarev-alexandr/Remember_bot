"""Яндекс Календарь через CalDAV."""

import logging
from datetime import datetime, timezone as dt_timezone

import caldav

from .base import CalendarProvider

logger = logging.getLogger(__name__)

CALDAV_URL = "https://caldav.yandex.ru/"


def _to_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_timezone.utc)
    return dt


def _rrule_to_dict(rrule_str: str) -> dict:
    """'FREQ=WEEKLY;BYDAY=MO,WE' -> {'freq': 'weekly', 'byday': ['mo','we']}."""
    d = {}
    for part in rrule_str.split(";"):
        k, _, v = part.partition("=")
        if k == "FREQ":
            d["freq"] = v.lower()
        elif k == "BYDAY":
            d["byday"] = [x.lower() for x in v.split(",")]
        elif k == "BYMONTHDAY":
            d["bymonthday"] = [int(x) for x in v.split(",")]
    return d


def _vrec_to_rrule_str(vrec) -> str:
    parts = []
    freq = vrec.get("FREQ")
    if freq:
        parts.append(f"FREQ={freq[0]}")
    byday = vrec.get("BYDAY")
    if byday:
        parts.append(f"BYDAY={','.join(str(x) for x in byday)}")
    bymonthday = vrec.get("BYMONTHDAY")
    if bymonthday:
        parts.append(f"BYMONTHDAY={','.join(str(x) for x in bymonthday)}")
    return ";".join(parts)


class YandexCalendarProvider(CalendarProvider):
    def __init__(self, connection):
        super().__init__(connection)
        self.username = connection.credentials.get("username", "")
        self.app_password = connection.credentials.get("app_password", "")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = caldav.DAVClient(
                url=CALDAV_URL, username=self.username, password=self.app_password
            )
        return self._client

    def validate(self):
        principal = self.client.principal()
        calendars = principal.calendars()
        if not calendars:
            raise ValueError("Календари не найдены")
        return str(calendars[0].url)

    def _calendar(self):
        principal = self.client.principal()
        if self.connection.calendar_id:
            return principal.calendar(cal_id=self.connection.calendar_id)
        return principal.calendars()[0]

    def list_events(self, since, until):
        cal = self._calendar()
        results = cal.date_search(start=since, end=until, expand=False)
        events = []
        for ev in results:
            norm = self._normalize(ev)
            if norm:
                events.append(norm)
        return events

    def _normalize(self, ev):
        try:
            component = ev.icalendar_component
            if component is None:
                return None
            summary = str(component.get("summary", ""))
            dtstart = component.get("dtstart")
            if dtstart is None:
                return None
            start = _to_aware(dtstart.dt)
            if not isinstance(start, datetime):
                return None  # событие без времени (только дата)
            rrule = None
            rrule_obj = component.get("rrule")
            if rrule_obj is not None:
                rrule = _vrec_to_rrule_str(rrule_obj)
            return {"id": str(ev.url), "summary": summary, "start": start, "rrule": rrule}
        except Exception:
            logger.exception("Ошибка разбора события CalDAV")
            return None

    def create_event(self, event):
        cal = self._calendar()
        ev = cal.add_event(
            summary=event["summary"],
            dtstart=event["start"],
            dtend=event["end"],
            rrule=_rrule_to_dict(event["rrule"]) if event.get("rrule") else None,
        )
        return str(ev.url)

    def update_event(self, external_id, event):
        ev = self._get_event(external_id)
        component = ev.icalendar_component
        component.pop("summary", None)
        component.add("summary", event["summary"])
        component.pop("dtstart", None)
        component.add("dtstart", event["start"])
        component.pop("dtend", None)
        component.add("dtend", event["end"])
        component.pop("rrule", None)
        if event.get("rrule"):
            component.add("rrule", _rrule_to_dict(event["rrule"]))
        ev.save()

    def delete_event(self, external_id):
        try:
            self._get_event(external_id).delete()
        except Exception:
            logger.exception("Ошибка удаления события CalDAV")

    def _get_event(self, external_id):
        cal = self._calendar()
        return cal.event_by_url(external_id)
