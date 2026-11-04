"""Database schema and engine. Postgres (Supabase) when DATABASE_URL is set, SQLite otherwise.

The same SQLAlchemy Core schema runs on both. Integrity lives in the database:
the partial unique indexes below make double booking impossible.
"""

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, MetaData,
                        String, Table, Text, create_engine, event, text)

from . import config

md = MetaData()


def _id():
    return Column("id", Integer, primary_key=True, autoincrement=True)


def _ts(name="created_at"):
    return Column(name, DateTime, nullable=False, default=config.now)


departments = Table("departments", md, _id(),
    Column("code", String(8), unique=True, nullable=False),
    Column("name", String(60), unique=True, nullable=False),
    Column("floor", String(20)), Column("description", Text))

doctors = Table("doctors", md, _id(),
    Column("code", String(10), unique=True, nullable=False),
    Column("name", String(80), nullable=False),
    Column("gender", String(10)),
    Column("department_id", ForeignKey("departments.id"), nullable=False),
    Column("qualification", String(80)), Column("experience_years", Integer),
    Column("languages", String(200), nullable=False),          # comma separated
    Column("fee_inr", Integer, nullable=False),
    Column("room", String(12), nullable=False),
    Column("consult_days", String(20), nullable=False),        # ISO weekdays "1,3,5"
    Column("start_time", String(5), nullable=False), Column("end_time", String(5), nullable=False),
    Column("slot_minutes", Integer, nullable=False, default=15),
    Column("bio", Text))

procedures = Table("procedures", md, _id(),
    Column("code", String(20), unique=True, nullable=False),
    Column("name", String(80), nullable=False),
    Column("category", String(10), nullable=False),            # MRI CT XRAY USG CARDIO ENDO LAB PKG
    Column("department_id", ForeignKey("departments.id")),
    Column("price_inr", Integer, nullable=False),
    Column("duration_minutes", Integer, nullable=False),
    Column("preauth_required", Boolean, nullable=False, default=False),
    Column("fasting_hours", Integer, default=0),
    Column("instructions", Text))

resources = Table("resources", md, _id(),
    Column("name", String(40), nullable=False),
    Column("category", String(10), nullable=False))

insurers = Table("insurers", md, _id(),
    Column("code", String(12), unique=True, nullable=False),
    Column("name", String(60), nullable=False),
    Column("mode", String(14), nullable=False),                # cashless / reimbursement / both
    Column("tpa_name", String(60)), Column("documents", Text), Column("notes", Text))

coverage_rules = Table("coverage_rules", md, _id(),
    Column("insurer_id", ForeignKey("insurers.id"), nullable=False),
    Column("procedure_id", ForeignKey("procedures.id")),
    Column("department_id", ForeignKey("departments.id")),
    Column("coverage", String(8), nullable=False),             # yes / partial / no
    Column("copay_percent", Integer, default=0),
    Column("cap_inr", Integer),
    Column("preauth_required", Boolean, nullable=False, default=False),
    Column("preauth_turnaround_hours", Integer, default=24))

hospital_info = Table("hospital_info", md,
    Column("topic", String(20), primary_key=True),
    Column("content", Text, nullable=False))

patients = Table("patients", md, _id(),
    Column("patient_code", String(12), unique=True, nullable=False),
    Column("full_name", String(80), nullable=False),
    Column("phone", String(16), unique=True, nullable=False),  # E.164 +91XXXXXXXXXX
    Column("date_of_birth", Date),
    Column("gender", String(12)),
    Column("email", String(120)),
    Column("address", String(160)),
    Column("preferred_language", String(20), default="English"),
    Column("preferred_time", String(10), default="any"),
    Column("insurer_id", ForeignKey("insurers.id")),
    Column("policy_number", String(30)),
    Column("caregiver_name", String(80)), Column("caregiver_relation", String(20)),
    Column("caregiver_phone", String(16)), Column("caregiver_email", String(120)),
    Column("caregiver_consent", Boolean, nullable=False, default=False),
    Column("mobility_needs", String(120)),
    Column("is_guest", Boolean, nullable=False, default=False),
    Column("password_hash", String(200)),
    Column("web_email", String(120), unique=True),             # website login email
    _ts())

verification_attempts = Table("verification_attempts", md, _id(),
    Column("phone", String(16), nullable=False),
    Column("success", Boolean, nullable=False), _ts("attempted_at"),
    Index("ix_verif_phone_time", "phone", "attempted_at"))

appointments = Table("appointments", md, _id(),
    Column("booking_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("doctor_id", ForeignKey("doctors.id")),
    Column("procedure_id", ForeignKey("procedures.id")),
    Column("resource_id", ForeignKey("resources.id")),
    Column("appt_date", Date, nullable=False),
    Column("appt_time", String(5), nullable=False),
    Column("status", String(12), nullable=False, default="booked"),  # booked cancelled completed no_show
    Column("reason", String(200)),
    Column("channel", String(10), nullable=False, default="chat"),   # chat voice web staff waitlist
    Column("idempotency_key", String(80), unique=True),
    _ts(), Column("updated_at", DateTime, default=config.now, onupdate=config.now),
    Column("cancelled_at", DateTime), Column("cancel_reason", String(200)),
    Index("ix_appt_patient", "patient_id", "status"),
    Index("ix_appt_date", "appt_date", "status"))
# the double-booking guards (one active booking per doctor slot / machine slot)
Index("uq_doctor_slot_booked", appointments.c.doctor_id, appointments.c.appt_date, appointments.c.appt_time,
      unique=True, postgresql_where=text("status = 'booked' AND doctor_id IS NOT NULL"),
      sqlite_where=text("status = 'booked' AND doctor_id IS NOT NULL"))
Index("uq_resource_slot_booked", appointments.c.resource_id, appointments.c.appt_date, appointments.c.appt_time,
      unique=True, postgresql_where=text("status = 'booked' AND resource_id IS NOT NULL"),
      sqlite_where=text("status = 'booked' AND resource_id IS NOT NULL"))

assistance_requests = Table("assistance_requests", md, _id(),
    Column("appointment_id", ForeignKey("appointments.id"), nullable=False),
    Column("type", String(16), nullable=False),
    Column("notes", String(200)), _ts())

waitlist = Table("waitlist", md, _id(),
    Column("code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("department_id", ForeignKey("departments.id")),
    Column("doctor_id", ForeignKey("doctors.id")),
    Column("date_from", Date, nullable=False), Column("date_to", Date, nullable=False),
    Column("time_preference", String(10), default="any"),
    Column("urgent", Boolean, nullable=False, default=False),
    Column("status", String(10), nullable=False, default="waiting"),  # waiting offered booked expired cancelled
    _ts(), Index("ix_waitlist_status", "status", "date_from", "date_to"))

waitlist_offers = Table("waitlist_offers", md, _id(),
    Column("offer_code", String(16), unique=True, nullable=False),
    Column("waitlist_id", ForeignKey("waitlist.id"), nullable=False),
    Column("doctor_id", ForeignKey("doctors.id"), nullable=False),
    Column("appt_date", Date, nullable=False), Column("appt_time", String(5), nullable=False),
    Column("status", String(10), nullable=False, default="open"),     # open accepted expired superseded
    Column("expires_at", DateTime, nullable=False),
    Column("appointment_id", ForeignKey("appointments.id")), _ts())
Index("uq_open_offer_per_slot", waitlist_offers.c.doctor_id, waitlist_offers.c.appt_date,
      waitlist_offers.c.appt_time, unique=True,
      postgresql_where=text("status = 'open'"), sqlite_where=text("status = 'open'"))

lab_reports = Table("lab_reports", md, _id(),
    Column("report_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("appointment_id", ForeignKey("appointments.id")),
    Column("doctor_id", ForeignKey("doctors.id")),
    Column("test_name", String(80), nullable=False),
    Column("status", String(10), nullable=False),                    # pending ready collected
    Column("ordered_at", DateTime, nullable=False),
    Column("expected_at", DateTime), Column("ready_at", DateTime),
    Column("summary", Text), Column("results", JSON),
    Index("ix_lab_patient", "patient_id", "ordered_at"))

prescriptions = Table("prescriptions", md, _id(),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("doctor_id", ForeignKey("doctors.id")),
    Column("medicine_name", String(80), nullable=False),
    Column("dosage", String(80)), Column("start_date", Date), Column("end_date", Date))

prescription_requests = Table("prescription_requests", md, _id(),
    Column("request_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("doctor_id", ForeignKey("doctors.id")),
    Column("medicine_name", String(80), nullable=False),
    Column("status", String(16), nullable=False, default="pending_doctor"), _ts())

bills = Table("bills", md, _id(),
    Column("bill_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("appointment_id", ForeignKey("appointments.id")),
    Column("description", String(120)),
    Column("amount_inr", Integer, nullable=False),
    Column("insurer_paid_inr", Integer, default=0),
    Column("status", String(16), nullable=False),                    # due paid partially_paid waived
    Column("due_date", Date), _ts(), Index("ix_bill_patient", "patient_id", "status"))

handoffs = Table("handoffs", md, _id(),
    Column("handoff_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id")),
    Column("phone", String(16)),
    Column("priority", String(8), nullable=False),
    Column("reason_code", String(20)),
    Column("summary", Text, nullable=False),
    Column("status", String(10), nullable=False, default="open"),
    Column("assigned_to", String(60)), _ts())

callbacks = Table("callbacks", md, _id(),
    Column("callback_code", String(12), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id")),
    Column("phone", String(16), nullable=False),
    Column("preferred_time", String(60)), Column("reason", String(200)),
    Column("status", String(10), nullable=False, default="queued"), _ts())

checkins = Table("checkins", md, _id(),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("appointment_id", ForeignKey("appointments.id")),
    Column("pain_score", Integer), Column("fever", Boolean), Column("symptoms_worse", Boolean),
    Column("notes", String(300)), Column("alert_raised", Boolean, nullable=False, default=False), _ts())

nurse_alerts = Table("nurse_alerts", md, _id(),
    Column("patient_id", ForeignKey("patients.id")),
    Column("phone", String(16)),
    Column("reason", String(300), nullable=False),
    Column("status", String(10), nullable=False, default="open"), _ts())

feedback = Table("feedback", md, _id(),
    Column("patient_id", ForeignKey("patients.id")),
    Column("appointment_id", ForeignKey("appointments.id")),
    Column("rating", Integer), Column("comment", String(500)), _ts())

interaction_notes = Table("interaction_notes", md, _id(),
    Column("patient_id", ForeignKey("patients.id")),
    Column("phone", String(16), nullable=False),
    Column("channel", String(10)),
    Column("summary", String(500), nullable=False),
    Column("topics", String(200)), Column("outcome", String(120)), _ts(),
    Index("ix_notes_patient", "patient_id", "created_at"))

# One searchable row per note, action or knowledge passage. Postgres adds three columns at startup
# (see setup_search): tsv (full-text, generated), chash (content hash, generated) and embedding vector(768).
search_docs = Table("search_docs", md, _id(),
    Column("ref", String(48), unique=True, nullable=False),       # note:12 / action:34 / kb:info:parking
    Column("kind", String(8), nullable=False),                    # note / action / kb
    Column("patient_id", Integer),                                # null for kb; always filtered, never cross-patient
    Column("title", String(160)),
    Column("body", Text, nullable=False), _ts(),
    Index("ix_search_patient", "patient_id", "created_at"), Index("ix_search_kind", "kind"))

resolutions = Table("resolutions", md, _id(),
    Column("patient_id", ForeignKey("patients.id")),
    Column("actor", String(30), nullable=False),     # agent / web / job:reminders / system
    Column("action", String(40), nullable=False),
    Column("ref", String(20)),
    Column("ok", Boolean, nullable=False),
    Column("summary", String(300)),
    Column("channel", String(10)), _ts(),
    Index("ix_res_patient", "patient_id", "created_at"), Index("ix_res_time", "created_at"))

outbound_calls = Table("outbound_calls", md, _id(),
    Column("call_code", String(12), unique=True, nullable=False),     # OC-48213, passed to the Studio flow as call_id
    Column("kind", String(30), nullable=False),                       # appointment_reminder, post_visit_followup, ...
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("appointment_id", ForeignKey("appointments.id")),
    Column("to_number", String(16), nullable=False),                  # number actually dialled (test number applied)
    Column("dedupe_key", String(80), unique=True, nullable=False),    # one call per reminder, ever
    Column("status", String(16), nullable=False, default="scheduled"),
    # scheduled -> dialing -> in_progress -> completed | retry -> ... | failed | simulated | cancelled
    Column("due_at", DateTime, nullable=False),
    Column("next_attempt_at", DateTime, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("interaction_id", String(64)),
    Column("last_event", String(30)),
    Column("outcome", String(30)),                                    # confirmed, reschedule_requested, feeling_well, ...
    Column("summary", Text), Column("prompt", Text), Column("error", String(300)),
    _ts(), Column("updated_at", DateTime), Column("completed_at", DateTime),
    Index("ix_outbound_due", "status", "next_attempt_at"), Index("ix_outbound_patient", "patient_id", "created_at"))

call_optouts = Table("call_optouts", md,
    Column("phone", String(16), primary_key=True),                   # patient's E.164 number
    Column("reason", String(120)), _ts())

# ------------------------------------------------------------------ pharmacy, HealthCredits wallet, payments
pharmacy_inventory = Table("pharmacy_inventory", md, _id(),
    Column("medicine_code", String(20), unique=True, nullable=False),
    Column("brand_name", String(80), nullable=False),
    Column("generic_name", String(120), nullable=False),
    Column("strength", String(40), nullable=False),
    Column("pack", String(40), nullable=False),                      # "strip of 15 tablets", "1 pen"
    Column("schedule_class", String(4), nullable=False),             # OTC H H1 X (Drugs and Cosmetics Rules)
    Column("chronic", Boolean, nullable=False, default=False),       # 30-day maintenance medicine: refill reminders
    Column("stock_qty", Integer, nullable=False, default=0),
    Column("unit_price_inr", Integer, nullable=False),
    Column("restock_eta", DateTime),
    Column("cold_chain", Boolean, nullable=False, default=False),    # 2-8 C, insulated pouch, OTP handover
    Column("alternative_code", String(20)),                          # in-stock bioequivalent generic
    Column("updated_at", DateTime))

pharmacy_orders = Table("pharmacy_orders", md, _id(),
    Column("order_code", String(16), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("items", JSON, nullable=False),                           # [{code, name, qty, unit_price, line_total, schedule}]
    Column("subtotal_inr", Integer, nullable=False), Column("delivery_fee_inr", Integer, nullable=False),
    Column("total_inr", Integer, nullable=False),
    Column("credits_used", Integer, nullable=False, default=0),
    Column("amount_due_inr", Integer, nullable=False, default=0),    # still to pay by link (split payment)
    Column("payment_link_code", String(16)),
    Column("delivery_address", String(200), nullable=False), Column("zone", String(10)),
    Column("status", String(16), nullable=False),  # awaiting_payment awaiting_stock confirmed dispatched delivered cancelled
    Column("cold_chain", Boolean, nullable=False, default=False),
    Column("eta", DateTime),
    Column("idempotency_key", String(80), unique=True),
    _ts(), Column("dispatched_at", DateTime), Column("updated_at", DateTime),
    Index("ix_pharm_patient", "patient_id", "created_at"))

health_credit_wallets = Table("health_credit_wallets", md,
    Column("patient_id", ForeignKey("patients.id"), primary_key=True),
    Column("balance", Integer, nullable=False, default=0),           # 1 HealthCredit = 1 rupee
    Column("updated_at", DateTime))

health_credit_txns = Table("health_credit_txns", md, _id(),
    Column("txn_code", String(20), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("direction", String(6), nullable=False),                  # credit debit
    Column("amount", Integer, nullable=False),
    Column("balance_after", Integer, nullable=False),
    Column("service", String(20), nullable=False),                   # pharmacy opd lab bill topup bonus refund
    Column("reference", String(40)),
    Column("idempotency_key", String(100), unique=True),             # a repeated request never debits twice
    _ts(), Index("ix_hc_patient", "patient_id", "created_at"))

payment_links = Table("payment_links", md, _id(),
    Column("link_code", String(16), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("purpose", String(16), nullable=False),                   # topup pharmacy bill
    Column("reference", String(40)),
    Column("amount_inr", Integer, nullable=False),
    Column("credits_to_add", Integer, nullable=False, default=0),    # top-ups: amount plus bonus
    Column("status", String(10), nullable=False, default="created"),  # created paid expired
    Column("provider", String(12)), Column("provider_id", String(64)), Column("provider_url", String(300)),
    _ts(), Column("paid_at", DateTime))

credit_refunds = Table("credit_refunds", md, _id(),
    Column("refund_code", String(16), unique=True, nullable=False),
    Column("patient_id", ForeignKey("patients.id"), nullable=False),
    Column("amount", Integer, nullable=False),
    Column("status", String(12), nullable=False, default="requested"),   # requested settled
    _ts())

# ------------------------------------------------------------------ calendar (Google Calendar + .ics)
calendar_events = Table("calendar_events", md, _id(),
    Column("ref", String(60), unique=True, nullable=False),         # WN-48213, PHARM-30219, refill:12, review:WN-1
    Column("patient_id", ForeignKey("patients.id")),
    Column("kind", String(16), nullable=False),                      # appointment delivery refill review
    Column("title", String(160), nullable=False),
    Column("starts_at", DateTime, nullable=False), Column("minutes", Integer, nullable=False, default=30),
    Column("all_day", Boolean, nullable=False, default=False),
    Column("details", Text), Column("location", String(200)),
    Column("attendees", JSON),                                       # [email, ...] patient + consented caregiver
    Column("sequence", Integer, nullable=False, default=0),          # iCalendar SEQUENCE: bumps on change
    Column("status", String(10), nullable=False, default="active"),  # active cancelled
    Column("google_event_id", String(120)),
    Column("sync_status", String(12), nullable=False, default="pending"),   # pending synced simulated failed
    Column("sync_error", String(300)), _ts(), Column("updated_at", DateTime))

notification_files = Table("notification_files", md, _id(),
    Column("notification_id", ForeignKey("notifications.id"), nullable=False),
    Column("filename", String(80), nullable=False),
    Column("mime", String(80), nullable=False),                      # text/calendar; method=REQUEST
    Column("content", Text, nullable=False))

notifications = Table("notifications", md, _id(),
    Column("patient_id", ForeignKey("patients.id")),
    Column("channel", String(10), nullable=False),   # email sms whatsapp voice_call
    Column("template", String(30), nullable=False),
    Column("to_address", String(120), nullable=False),
    Column("subject", String(200)), Column("body", Text),
    Column("status", String(10), nullable=False, default="queued"),  # queued sent failed simulated
    Column("dedupe_key", String(80), unique=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error", String(300)), _ts(), Column("sent_at", DateTime),
    Index("ix_notif_status", "status", "created_at"))


# ------------------------------------------------------------------ engine
def _make_engine():
    url = config.DATABASE_URL
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        # prepare_threshold=None: required behind Supabase's transaction pooler (PgBouncer mode)
        return create_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=300,
                             connect_args={"prepare_threshold": None, "connect_timeout": 10})
    eng = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False, "timeout": 15})

    @event.listens_for(eng, "connect")
    def _pragmas(con, _):
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()
    return eng


engine = _make_engine()
IS_POSTGRES = engine.dialect.name == "postgresql"
DB_ERROR: str | None = None


def fallback_to_sqlite(reason: str) -> None:
    """Postgres is unreachable at startup: keep the site and the Talkdesk tools up on local SQLite.
    /health reports the reason so the misconfiguration is visible."""
    global engine, IS_POSTGRES, DB_ERROR
    saved = config.DATABASE_URL
    config.DATABASE_URL = ""
    engine = _make_engine()
    config.DATABASE_URL = saved
    IS_POSTGRES = False
    DB_ERROR = reason


def create_schema():
    md.create_all(engine)
    if IS_POSTGRES:
        lock_down()
        setup_search()


# ------------------------------------------------------------------ hybrid search capabilities
SEARCH = {"fts": False, "trgm": False, "vector": False, "path": "public", "error": None}


def _ext_schema(c, name: str) -> str | None:
    return c.execute(text("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
                          "WHERE e.extname = :n"), {"n": name}).scalar()


def _try_extension(name: str) -> str | None:
    """Enable an extension if allowed (Supabase lets the postgres role create vector and pg_trgm,
    preferably in the 'extensions' schema). Returns the schema it lives in, or None."""
    try:
        with engine.begin() as c:
            found = _ext_schema(c, name)
            if found:
                return found
            has_ext_schema = c.execute(text("SELECT 1 FROM pg_namespace WHERE nspname = 'extensions'")).scalar()
            c.execute(text(f"CREATE EXTENSION IF NOT EXISTS {name}" + (" WITH SCHEMA extensions" if has_ext_schema else "")))
            return _ext_schema(c, name)
    except Exception as e:
        SEARCH["error"] = f"{name}: {str(e).splitlines()[0][:160]}"
        return None


def setup_search() -> dict:
    """Idempotent DDL for hybrid search. Each leg is optional: if an extension can't be enabled, that leg is off
    and search still works with the others. Never raises."""
    from . import config
    trgm, vec = _try_extension("pg_trgm"), _try_extension("vector")
    schemas = ["public"] + [s for s in dict.fromkeys([trgm, vec]) if s and s != "public"]
    SEARCH["path"] = ", ".join(schemas)
    dim = config.EMBEDDINGS_DIM
    steps = [
        ("fts", ["ALTER TABLE search_docs ADD COLUMN IF NOT EXISTS tsv tsvector GENERATED ALWAYS AS "
                 "(to_tsvector('english', coalesce(title, '') || ' ' || body)) STORED",
                 "CREATE INDEX IF NOT EXISTS ix_search_tsv ON search_docs USING gin (tsv)",
                 "ALTER TABLE search_docs ADD COLUMN IF NOT EXISTS chash text GENERATED ALWAYS AS "
                 "(md5(coalesce(title, '') || '|' || body)) STORED"]),
        ("trgm", ["CREATE INDEX IF NOT EXISTS ix_search_trgm ON search_docs USING gin (body gin_trgm_ops)"] if trgm else None),
        ("vector", [f"ALTER TABLE search_docs ADD COLUMN IF NOT EXISTS embedding vector({dim})",
                    # Knowledge passages are searched across the whole table, so they get an ANN index. Patient
                    # rows are always filtered to one patient (a handful of rows) and scored exactly instead.
                    "CREATE INDEX IF NOT EXISTS ix_search_vec_kb ON search_docs USING hnsw (embedding vector_cosine_ops) "
                    "WHERE kind = 'kb'",
                    # Survives /ops/reset-demo (not in the SQLAlchemy metadata), so re-seeding re-uses embeddings
                    # instead of spending API quota again. Keyed by model + content hash.
                    f"CREATE TABLE IF NOT EXISTS embedding_cache (model text NOT NULL, chash text NOT NULL, "
                    f"embedding vector({dim}) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), "
                    "PRIMARY KEY (model, chash))",
                    "ALTER TABLE embedding_cache ENABLE ROW LEVEL SECURITY"] if vec else None),
    ]
    for leg, sqls in steps:
        if not sqls:
            continue
        try:
            with engine.begin() as c:
                c.execute(text(f"SET LOCAL search_path TO {SEARCH['path']}"))
                for s in sqls:
                    c.execute(text(s))
            SEARCH[leg] = True
        except Exception as e:
            SEARCH[leg] = False
            SEARCH["error"] = f"{leg}: {str(e).splitlines()[0][:160]}"
    return SEARCH


def lock_down() -> None:
    """Supabase exposes tables in the public schema through its REST API (anon key).
    Enable Row Level Security with no policies so that API sees nothing. Our server connects as the
    table owner (postgres), which bypasses RLS, so the app keeps full access. Idempotent."""
    with engine.begin() as c:
        for name in md.tables:
            c.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        c.execute(text("""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
                EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
              END IF;
            END $$;"""))


def drop_schema():
    md.drop_all(engine)


def db_target() -> dict | None:
    """What DATABASE_URL was parsed as (user, host, port, database, password length): never the password itself."""
    if not config.DATABASE_URL:
        return None
    from sqlalchemy.engine import make_url
    try:
        u = make_url(config.DATABASE_URL.replace("postgres://", "postgresql://", 1))
        pw = u.password or ""
        return {"user": u.username, "host": u.host, "port": u.port, "database": u.database, "password_length": len(pw),
                "password_has_brackets": "[" in pw or "]" in pw, "password_has_spaces": pw != pw.strip()}
    except Exception as e:
        return {"parse_error": str(e)[:120]}


def db_ok() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False
