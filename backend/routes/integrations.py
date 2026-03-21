"""Blueprint for external integration and scheduler management routes."""

from flask import Blueprint, jsonify, request
import db

bp = Blueprint("integrations", __name__)

# ---------------------------------------------------------------------------
# Integration status helpers
# ---------------------------------------------------------------------------

SOURCES = ["remotive", "themuse", "hn_hiring", "weworkremotely", "workingnomads"]


def _last_sync(source: str) -> str | None:
    row = db.query_one(
        "SELECT MAX(created_at) AS last FROM fresh_jobs WHERE source = %s",
        (source,),
    )
    return row["last"].isoformat() if row and row.get("last") else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/api/integrations/status", methods=["GET"])
def integrations_status():
    """List all integration sources with last sync time and job count."""
    statuses = []
    for source in SOURCES:
        count_row = db.query_one(
            "SELECT COUNT(*) AS cnt FROM fresh_jobs WHERE source = %s", (source,)
        )
        statuses.append({
            "source": source,
            "last_sync": _last_sync(source),
            "total_jobs": count_row["cnt"] if count_row else 0,
        })
    return jsonify({"integrations": statuses})


@bp.route("/api/integrations/sync/<source>", methods=["POST"])
def trigger_sync(source: str):
    """Manually trigger a sync for a specific source."""
    try:
        if source == "remotive":
            from integrations.remotive import sync_remotive_to_inbox
            body = request.get_json(silent=True) or {}
            result = sync_remotive_to_inbox(
                search=body.get("search"),
                category=body.get("category"),
                limit=int(body.get("limit", 20)),
            )
        elif source == "themuse":
            from integrations.themuse import sync_muse_to_inbox
            body = request.get_json(silent=True) or {}
            result = sync_muse_to_inbox(
                category=body.get("category"),
                level=body.get("level"),
                location=body.get("location"),
            )
        elif source == "hn":
            from integrations.hn_hiring import sync_hn_to_inbox
            body = request.get_json(silent=True) or {}
            result = sync_hn_to_inbox(months_back=int(body.get("months_back", 1)))
        elif source == "rss":
            from integrations.rss_feeds import sync_all_rss_feeds
            result = sync_all_rss_feeds()
        else:
            return jsonify({"error": f"Unknown source: {source}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok", "result": result})


@bp.route("/api/integrations/jobs", methods=["GET"])
def list_integration_jobs():
    """List jobs from fresh_jobs with optional source/keyword filters."""
    source = request.args.get("source")
    keyword = request.args.get("keyword", "")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    conditions = []
    params = []

    if source:
        conditions.append("source = %s")
        params.append(source)
    if keyword:
        conditions.append("(title ILIKE %s OR company ILIKE %s)")
        params += [f"%{keyword}%", f"%{keyword}%"]

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]

    rows = db.query(
        f"""SELECT id, title, company, location, source, salary_range, url, created_at
            FROM fresh_jobs {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params),
    )
    return jsonify({"jobs": rows or [], "limit": limit, "offset": offset})


# ---------------------------------------------------------------------------
# Scheduler routes
# ---------------------------------------------------------------------------

@bp.route("/api/scheduler/jobs", methods=["GET"])
def scheduler_jobs():
    """List all scheduled jobs with status."""
    try:
        from scheduler import scheduler
        jobs = scheduler.list_jobs()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"jobs": jobs})


@bp.route("/api/scheduler/jobs/<name>/toggle", methods=["POST"])
def toggle_scheduler_job(name: str):
    """Enable or disable a scheduled job by name."""
    try:
        from scheduler import scheduler
        result = scheduler.toggle_job(name)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if result is None:
        return jsonify({"error": f"Job '{name}' not found"}), 404
    return jsonify({"job": result})
