"""Booking email + calendar: only promise an email that will really be sent; demo override reaches calendar guests."""

from app import config, notify
from app.services import calendar as cal


def test_will_email_needs_a_transport(monkeypatch):
    monkeypatch.setattr(notify, "transport", lambda: "none")
    assert not notify.will_email("someone@gmail.com")
    monkeypatch.setattr(notify, "transport", lambda: "smtp")
    assert notify.will_email("someone@gmail.com")
    assert not notify.will_email("fake@example.com")
    assert not notify.will_email("")


def test_demo_override_applies_to_email_and_calendar(monkeypatch):
    monkeypatch.setattr(notify, "transport", lambda: "smtp")
    monkeypatch.setattr(config, "DEMO_EMAIL_OVERRIDE", "")
    assert not notify.will_email("rahul.demo@example.com")
    assert cal.attendees_for({"email": "rahul.demo@example.com"}) == []
    monkeypatch.setattr(config, "DEMO_EMAIL_OVERRIDE", "Inbox@Gmail.com")
    assert notify.will_email("rahul.demo@example.com")
    assert cal.attendees_for({"email": "rahul.demo@example.com"}) == ["inbox@gmail.com"]
    assert cal.attendees_for({"email": "real@gmail.com"}) == ["real@gmail.com"]
