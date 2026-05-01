import os
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


TIMEZONE_NAME = os.getenv("MOOD_TIMEZONE", "Asia/Taipei")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)


def today_local() -> date:
    return datetime.now(TIMEZONE).date()


def parse_hhmm(value: str, default: str = "22:00") -> time:
    raw = (value or default).strip()
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return time(hour=hour, minute=minute, tzinfo=TIMEZONE)
    except ValueError:
        fallback_hour, fallback_minute = default.split(":", 1)
        return time(hour=int(fallback_hour), minute=int(fallback_minute), tzinfo=TIMEZONE)
