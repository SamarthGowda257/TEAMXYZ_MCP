"""Event handlers (the background workers). Each is idempotent: running it twice gives the same result."""

import logging
import time

from sqlalchemy import select

from . import config, db, notify
from .events import on
from .services import blackboard as bb
from .services import patients as pt
from .services.ref import REF
from .store import store

log = logging.getLogger("wellnest.workers")


def _patient(pid):
    with db.engine.connect() as c:
        return pt.get_by_id(c, pid)


def _count(kind: str) -> None:
    store.incr(f"stats:{time.strftime('%Y-%m-%d')}:{kind}", 1, 3 * 24 * 3600)


# ------------------------------------------------------------------ context preloader
def preload(pid) -> None:
    p = _patient(pid)
    if not p or not p["date_of_birth"]:
        return
    r = bb.ref_for(p["phone"])
    for item in ("snapshot", "profile", "memory"):
        bb.mark(None, item, "LOADING", "preloader", ref=r)
    try:
        if not bb.get_snapshot(p["phone"]):
            with db.engine.connect() as c:
                bb.put_snapshot(p["phone"], pt.snapshot(c, p), source="preloader")
        ins = REF.insurers.get(p["insurer_id"]) if p["insurer_id"] else None
        bb.put_profile(p["phone"], {
            "preferred_language": p["preferred_language"], "preferred_time": p["preferred_time"],
            "insurer": ins["name"] if ins else None, "caregiver_on_file": bool(p["caregiver_name"]),
            "caregiver_consent": p["caregiver_consent"], "mobility_needs": p["mobility_needs"], "is_senior": pt.is_senior(p)})
        refresh_memory(pid, p)
    except Exception as e:
        for item in ("snapshot", "profile", "memory"):
            bb.mark(None, item, "ERROR", "preloader", ref=r)
        raise e


def refresh_memory(pid, p=None) -> None:
    p = p or _patient(pid)
    if not p:
        return
    N = db.interaction_notes
    with db.engine.connect() as c:
        rows = c.execute(select(N.c.summary, N.c.created_at).where(N.c.patient_id == pid)
                         .order_by(N.c.created_at.desc()).limit(5)).all()
    bb.put_memory(p["phone"], [f"{r[1].strftime('%d %b')}: {r[0]}" for r in rows])


@on("patient.verified")
def _verified(e):
    preload(e["patient_id"])
    _count("patient.verified")


@on("session.warm")
def _warm(e):
    preload(e["patient_id"])
    _count("session.warm")


# ------------------------------------------------------------------ context updater
def _changed(e, kind):
    p = _patient(e["patient_id"])
    if p:
        bb.invalidate(p["phone"], "p1")
        if p["date_of_birth"]:
            with db.engine.connect() as c:
                bb.put_snapshot(p["phone"], pt.snapshot(c, p), source="context-updater")
    _count(kind)


@on("appointment.created")
def _created(e):
    _changed(e, "appointment.created")


@on("appointment.cancelled")
def _cancelled(e):
    _changed(e, "appointment.cancelled")


@on("appointment.rescheduled")
def _rescheduled(e):
    _changed(e, "appointment.rescheduled")


@on("waitlist.offered")
def _offered(e):
    _changed(e, "waitlist.offered")


@on("waitlist.accepted")
def _accepted(e):
    _changed(e, "waitlist.accepted")


@on("preferences.updated")
def _prefs(e):
    p = _patient(e["patient_id"])
    if p:
        bb.invalidate(p["phone"], "p1", "p2")
    _count("preferences.updated")


# ------------------------------------------------------------------ notification + memory + analytics
@on("notification.queued")
def _notify(e):
    notify.wake()
    _count("notification.queued")


@on("interaction.noted")
def _noted(e):
    if e.get("patient_id"):
        refresh_memory(e["patient_id"])
    _count("interaction.noted")


@on("handoff.created")
def _handoff(e):
    _count("handoff." + str(e.get("priority", "normal")))


def todays_counts() -> dict:
    prefix = f"stats:{time.strftime('%Y-%m-%d')}:"
    out = {}
    for k in store.scan(prefix, 100):
        v = store.get_json(k, count=False)
        if v is not None:
            out[k[len(prefix):]] = int(v)
    return out
