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


def _make_check_stale():
    def fn():
        try:
            import db
            rows = db.query(
                """SELECT id, company, position FROM applications
                   WHERE updated_at < NOW() - INTERVAL '14 days'
                     AND status NOT IN ('offer','rejected','withdrawn')""",
            )
            for row in (rows or []):
                db.query(
                    """INSERT INTO notifications (type, message, metadata)
                       VALUES ('stale_application', %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (
                        f"Application to {row['company']} ({row['position']}) has no update in 14+ days",
                        str({"application_id": row["id"]}),
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
    s.add_job("check_stale_applications", _make_check_stale(), interval_minutes=60)
    s.add_job("check_posting_status", _noop("check_posting_status"), interval_minutes=720)
    return s


# Module-level singleton — imported by app.py
scheduler = build_scheduler()
