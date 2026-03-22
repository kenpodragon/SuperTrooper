"""Simple threading-based scheduler (no APScheduler dependency)."""

import threading
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class _Job:
    def __init__(self, name: str, func, interval_minutes: int, enabled: bool = True):
        self.name = name
        self.func = func
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.next_run: datetime = datetime.utcnow()

    def is_due(self) -> bool:
        return self.enabled and datetime.utcnow() >= self.next_run

    def mark_run(self):
        self.last_run = datetime.utcnow()
        self.next_run = self.last_run + timedelta(minutes=self.interval_minutes)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "interval_minutes": self.interval_minutes,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat(),
        }


class SimpleScheduler:
    """Background thread that polls registered jobs and runs them when due."""

    POLL_INTERVAL = 30  # seconds

    def __init__(self):
        self._jobs: dict[str, _Job] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def add_job(self, name: str, func, interval_minutes: int, enabled: bool = True):
        self._jobs[name] = _Job(name, func, interval_minutes, enabled)
        logger.info(f"Scheduler: registered job '{name}' every {interval_minutes} min")

    def remove_job(self, name: str):
        self._jobs.pop(name, None)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SimpleScheduler")
        self._thread.start()
        logger.info("Scheduler started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def list_jobs(self) -> list:
        return [j.to_dict() for j in self._jobs.values()]

    def toggle_job(self, name: str) -> dict | None:
        job = self._jobs.get(name)
        if not job:
            return None
        job.enabled = not job.enabled
        return job.to_dict()

    def _run_loop(self):
        while not self._stop_event.is_set():
            for job in list(self._jobs.values()):
                if job.is_due():
                    try:
                        logger.info(f"Scheduler: running '{job.name}'")
                        job.func()
                        job.mark_run()
                    except Exception as e:
                        logger.error(f"Scheduler: job '{job.name}' failed: {e}")
                        job.mark_run()  # still advance to avoid tight retry loop
            self._stop_event.wait(self.POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Lazy job definitions — imported here to avoid circular imports at module load
# ---------------------------------------------------------------------------

def _noop(label):
    def fn():
        logger.info(f"Placeholder job '{label}' ran (no-op)")
    return fn


def _make_follow_up_cadence():
    """S6.1 — Follow-up cadence engine.

    Two rules:
    - Applied but no response in 7 days  → follow_up_due notification
    - Interview completed but no response in 3 days → follow_up_due notification

    Deduplicates: skips if an unread follow_up_due notification already exists
    for the same application created in the last 7 days.
    """
    def fn():
        try:
            import db

            # Rule 1: Applied, no status change in 7+ days
            applied_stale = db.query(
                """
                SELECT id, company_name, role,
                       EXTRACT(DAY FROM NOW() - last_status_change)::int AS days_waiting
                FROM applications
                WHERE status = 'Applied'
                  AND last_status_change < NOW() - INTERVAL '7 days'
                  AND posting_closed = FALSE
                """
            )
            # Rule 2: Interviewing (completed), no status change in 3+ days
            interview_stale = db.query(
                """
                SELECT id, company_name, role,
                       EXTRACT(DAY FROM NOW() - last_status_change)::int AS days_waiting
                FROM applications
                WHERE status IN ('Interviewing', 'Phone Screen', 'Technical', 'Final')
                  AND last_status_change < NOW() - INTERVAL '3 days'
                  AND posting_closed = FALSE
                """
            )

            created = 0
            for app in (applied_stale or []):
                # Skip if recent unread notification already exists
                existing = db.query_one(
                    """
                    SELECT id FROM notifications
                    WHERE type = 'follow_up_due'
                      AND entity_type = 'application'
                      AND entity_id = %s
                      AND dismissed = FALSE
                      AND created_at > NOW() - INTERVAL '7 days'
                    """,
                    (app["id"],),
                )
                if existing:
                    continue
                days = app.get("days_waiting") or 7
                company = app.get("company_name") or "Unknown"
                role = app.get("role") or "Unknown Role"
                db.execute_returning(
                    """
                    INSERT INTO notifications
                        (type, severity, title, body, link, entity_type, entity_id)
                    VALUES (%s, %s, %s, %s, %s, 'application', %s)
                    RETURNING id
                    """,
                    (
                        "follow_up_due",
                        "action_needed",
                        f"Follow up on your application to {company}",
                        f"You applied for {role} at {company} {days} days ago with no response. "
                        "Consider sending a follow-up email.",
                        f"/pipeline/{app['id']}",
                        app["id"],
                    ),
                )
                created += 1

            for app in (interview_stale or []):
                existing = db.query_one(
                    """
                    SELECT id FROM notifications
                    WHERE type = 'follow_up_due'
                      AND entity_type = 'application'
                      AND entity_id = %s
                      AND dismissed = FALSE
                      AND created_at > NOW() - INTERVAL '7 days'
                    """,
                    (app["id"],),
                )
                if existing:
                    continue
                days = app.get("days_waiting") or 3
                company = app.get("company_name") or "Unknown"
                role = app.get("role") or "Unknown Role"
                db.execute_returning(
                    """
                    INSERT INTO notifications
                        (type, severity, title, body, link, entity_type, entity_id)
                    VALUES (%s, %s, %s, %s, %s, 'application', %s)
                    RETURNING id
                    """,
                    (
                        "follow_up_due",
                        "action_needed",
                        f"Send thank-you/follow-up to {company}",
                        f"Your interview for {role} at {company} was {days} days ago with no update. "
                        "Send a thank-you note or status check.",
                        f"/pipeline/{app['id']}",
                        app["id"],
                    ),
                )
                created += 1

            logger.info(
                f"follow_up_cadence: {len(applied_stale or [])} applied-stale, "
                f"{len(interview_stale or [])} interview-stale, {created} notifications created"
            )
        except Exception as e:
            logger.error(f"follow_up_cadence error: {e}")
    return fn


def _make_weekly_digest_notification():
    """S6.3 — Create a weekly digest notification summarising pipeline activity."""
    def fn():
        try:
            import db
            # Suppress if a digest_ready notification was created in the last 6 days
            recent = db.query_one(
                """
                SELECT id FROM notifications
                WHERE type = 'digest_ready'
                  AND created_at > NOW() - INTERVAL '6 days'
                """
            )
            if recent:
                logger.info("weekly_digest_notification: digest already sent this week, skipping")
                return

            # Quick pipeline snapshot
            snapshot = db.query_one(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'Applied') AS applied,
                    COUNT(*) FILTER (WHERE status IN ('Phone Screen','Interviewing','Technical','Final')) AS in_progress,
                    COUNT(*) FILTER (WHERE status = 'Offer') AS offers,
                    COUNT(*) FILTER (WHERE status = 'Rejected') AS rejected,
                    COUNT(*) FILTER (WHERE date_applied >= NOW() - INTERVAL '7 days') AS new_this_week
                FROM applications
                WHERE status NOT IN ('draft', 'withdrawn', 'archived')
                """
            )
            new_fresh = db.query_one(
                "SELECT COUNT(*)::int AS count FROM fresh_jobs WHERE discovered_at >= NOW() - INTERVAL '7 days'"
            )

            if not snapshot:
                return

            total = snapshot.get("total") or 0
            in_progress = snapshot.get("in_progress") or 0
            offers = snapshot.get("offers") or 0
            new_apps = snapshot.get("new_this_week") or 0
            new_jobs = new_fresh["count"] if new_fresh else 0

            body = (
                f"This week: {new_apps} new application(s), {new_jobs} new job(s) in inbox. "
                f"Pipeline: {total} active, {in_progress} in progress, {offers} offer(s)."
            )

            db.execute_returning(
                """
                INSERT INTO notifications
                    (type, severity, title, body, link)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    "digest_ready",
                    "info",
                    "Weekly Pipeline Digest",
                    body,
                    "/analytics",
                ),
            )
            logger.info(f"weekly_digest_notification: created digest — {body}")
        except Exception as e:
            logger.error(f"weekly_digest_notification error: {e}")
    return fn


def _make_check_stale():
    """Legacy 14-day stale check kept for backward compatibility.
    Follow-up cadence engine (above) is the primary S6.1 implementation.
    """
    def fn():
        try:
            import db
            rows = db.query(
                """
                SELECT id, company_name, role
                FROM applications
                WHERE last_status_change < NOW() - INTERVAL '14 days'
                  AND status NOT IN ('Offer', 'Rejected', 'Withdrawn', 'Archived')
                """,
            )
            for row in (rows or []):
                existing = db.query_one(
                    """
                    SELECT id FROM notifications
                    WHERE type = 'stale_warning'
                      AND entity_type = 'application'
                      AND entity_id = %s
                      AND created_at > NOW() - INTERVAL '7 days'
                    """,
                    (row["id"],),
                )
                if existing:
                    continue
                company = row.get("company_name") or "Unknown"
                role = row.get("role") or "Unknown Role"
                db.execute_returning(
                    """
                    INSERT INTO notifications
                        (type, severity, title, body, link, entity_type, entity_id)
                    VALUES (%s, %s, %s, %s, %s, 'application', %s)
                    RETURNING id
                    """,
                    (
                        "stale_warning",
                        "action_needed",
                        f"Stale application: {company}",
                        f"Your {role} application at {company} has had no activity for 14+ days.",
                        f"/pipeline/{row['id']}",
                        row["id"],
                    ),
                )
            logger.info(f"check_stale_applications: checked {len(rows or [])} stale apps")
        except Exception as e:
            logger.error(f"check_stale_applications error: {e}")
    return fn


def _make_sync_remotive():
    def fn():
        from integrations.remotive import sync_remotive_to_inbox
        result = sync_remotive_to_inbox(limit=30)
        logger.info(f"sync_remotive: {result}")
    return fn


def _make_sync_muse():
    def fn():
        from integrations.themuse import sync_muse_to_inbox
        result = sync_muse_to_inbox()
        logger.info(f"sync_muse: {result}")
    return fn


def _make_sync_rss():
    def fn():
        from integrations.rss_feeds import sync_all_rss_feeds
        result = sync_all_rss_feeds()
        logger.info(f"sync_rss: {result}")
    return fn


def _make_sync_hn():
    def fn():
        from integrations.hn_hiring import sync_hn_to_inbox
        result = sync_hn_to_inbox(months_back=1)
        logger.info(f"sync_hn: {result}")
    return fn


def build_scheduler() -> SimpleScheduler:
    """Create and configure the default scheduler with all pre-registered jobs."""
    s = SimpleScheduler()
    s.add_job("sync_remotive", _make_sync_remotive(), interval_minutes=360)
    s.add_job("sync_muse", _make_sync_muse(), interval_minutes=360)
    s.add_job("sync_rss_feeds", _make_sync_rss(), interval_minutes=180)
    s.add_job("sync_hn_hiring", _make_sync_hn(), interval_minutes=1440)
    # S6.1 — Follow-up cadence (7-day applied, 3-day post-interview)
    s.add_job("follow_up_cadence", _make_follow_up_cadence(), interval_minutes=120)
    # S6.3 — Weekly pipeline digest notification (runs every 24h, self-deduplicates to once/week)
    s.add_job("weekly_digest_notification", _make_weekly_digest_notification(), interval_minutes=1440)
    # Legacy 14-day stale warning (kept; cadence engine handles the primary S6.1 logic)
    s.add_job("check_stale_applications", _make_check_stale(), interval_minutes=60)
    s.add_job("check_posting_status", _noop("check_posting_status"), interval_minutes=720)
    return s


# Module-level singleton — imported by app.py
scheduler = build_scheduler()
