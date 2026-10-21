"""Google Calendar через REST API (OAuth 2.0)."""

import logging
from datetime import datetime

import requests

from .base import CalendarProvider

logger = logging.getLogger(__name__)

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _iso(dt):
    return dt.isoformat()


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self, connection):
        super().__init__(connection)
        self._creds = dict(connection.credentials or {})
        self._access_token = self._creds.get("token")

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self):
        data = {
            "client_id": self._creds["client_id"],
            "client_secret": self._creds["client_secret"],
            "refresh_token": self._creds["refresh_token"],
            "grant_type": "refresh_token",
        }
        resp = requests.post(TOKEN_URI, data=data, timeout=30)
        resp.raise_for_status()
        token = resp.json()
        self._access_token = token["access_token"]
        self._creds["token"] = token["access_token"]
        self.connection.credentials = self._creds
        self.connection.save(update_fields=["credentials"])

    def _request(self, method, url, **kwargs):
        resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if resp.status_code == 401:
            self._refresh()
            resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    @property
    def calendar_id(self):
        return self.connection.calendar_id or "primary"

    def validate(self):
        resp = self._request("GET", f"{CALENDAR_API}/calendars/{self.calendar_id}")
        return resp.json().get("id", "primary")

    def list_events(self, since, until):
        url = f"{CALENDAR_API}/calendars/{self.calendar_id}/events"
        params = {
            "timeMin": _iso(since),
            "timeMax": _iso(until),
            "singleEvents": "false",
            "maxResults": "2500",
        }
        events = []
        page_token = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            data = self._request("GET", url, params=params).json()
            for item in data.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                norm = self._normalize(item)
                if norm:
                    events.append(norm)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return events

    @staticmethod
    def _normalize(item):
        start_raw = (item.get("start") or {}).get("dateTime")
        if not start_raw:
            return None  # события на весь день пропускаем
        rrule = None
        recurrence = item.get("recurrence") or []
        if recurrence:
            rrule = recurrence[0].replace("RRULE:", "", 1)
        return {
            "id": item["id"],
            "summary": item.get("summary", ""),
            "start": datetime.fromisoformat(start_raw),
            "rrule": rrule,
        }

    def create_event(self, event):
        body = self._to_google(event)
        resp = self._request("POST", f"{CALENDAR_API}/calendars/{self.calendar_id}/events", json=body)
        return resp.json()["id"]

    def update_event(self, external_id, event):
        body = self._to_google(event)
        self._request(
            "PUT", f"{CALENDAR_API}/calendars/{self.calendar_id}/events/{external_id}", json=body
        )

    def delete_event(self, external_id):
        try:
            self._request("DELETE", f"{CALENDAR_API}/calendars/{self.calendar_id}/events/{external_id}")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                return
            raise

    @staticmethod
    def _to_google(event):
        body = {
            "summary": event["summary"],
            "start": {"dateTime": _iso(event["start"]), "timeZone": event.get("timezone", "UTC")},
            "end": {"dateTime": _iso(event["end"]), "timeZone": event.get("timezone", "UTC")},
        }
        if event.get("rrule"):
            body["recurrence"] = [f"RRULE:{event['rrule']}"]
        return body
