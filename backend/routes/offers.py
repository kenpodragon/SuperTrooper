"""Routes for Offer Evaluation & Negotiation."""

import json
import math
from flask import Blueprint, request, jsonify
import db

bp = Blueprint("offers", __name__)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@bp.route("/api/offers", methods=["POST"])
def create_offer():
    """Log a new offer.

    Body (JSON): application_id (required), plus any offer fields.
    """
    data = request.get_json(force=True)
    application_id = data.get("application_id")
    if not application_id:
        return jsonify({"error": "application_id is required"}), 400

    # Verify application exists
    app = db.query_one("SELECT id FROM applications WHERE id = %s", (application_id,))
    if not app:
        return jsonify({"error": "Application not found"}), 404

    row = db.execute_returning(
        """
        INSERT INTO offers
            (application_id, version, version_label, base_salary, signing_bonus,
             annual_bonus_pct, annual_bonus_target, equity_type, equity_value,
             equity_shares, equity_vesting_months, equity_cliff_months,
             benefits_notes, pto_days, remote_policy, title_offered,
             start_date, expiration_date, location, status,
             negotiation_notes, decision_factors)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            application_id,
            data.get("version", 1),
            data.get("version_label", "initial"),
            data.get("base_salary"),
            data.get("signing_bonus"),
            data.get("annual_bonus_pct"),
            data.get("annual_bonus_target"),
            data.get("equity_type"),
            data.get("equity_value"),
            data.get("equity_shares"),
            data.get("equity_vesting_months", 48),
            data.get("equity_cliff_months", 12),
            data.get("benefits_notes"),
            data.get("pto_days"),
            data.get("remote_policy"),
            data.get("title_offered"),
            data.get("start_date"),
            data.get("expiration_date"),
            data.get("location"),
            data.get("status", "pending"),
            data.get("negotiation_notes"),
            json.dumps(data["decision_factors"]) if data.get("decision_factors") else None,
        ),
    )
    return jsonify(row), 201


@bp.route("/api/offers", methods=["GET"])
def list_offers():
    """List offers with optional filters.

    Query params: application_id, status
    """
    application_id = request.args.get("application_id")
    status = request.args.get("status")

    clauses, params = [], []
    if application_id:
        clauses.append("o.application_id = %s")
        params.append(int(application_id))
    if status:
        clauses.append("o.status = %s")
        params.append(status)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.query(
        f"""
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        {where}
        ORDER BY o.created_at DESC
        """,
        params,
    )
    return jsonify(rows), 200


@bp.route("/api/offers/<int:offer_id>", methods=["GET"])
def get_offer(offer_id):
    """Get a single offer by ID."""
    row = db.query_one(
        """
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id = %s
        """,
        (offer_id,),
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


@bp.route("/api/offers/<int:offer_id>", methods=["PUT", "PATCH"])
def update_offer(offer_id):
    """Update offer fields.

    Body (JSON): any subset of updatable offer fields.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = [
        "base_salary", "signing_bonus", "annual_bonus_pct", "annual_bonus_target",
        "equity_type", "equity_value", "equity_shares", "equity_vesting_months",
        "equity_cliff_months", "benefits_notes", "pto_days", "remote_policy",
        "title_offered", "start_date", "expiration_date", "location", "status",
        "negotiation_notes", "decision_factors", "version_label",
    ]
    sets, params = [], []
    for field in allowed:
        if field in data:
            val = data[field]
            if field == "decision_factors" and val is not None:
                val = json.dumps(val)
            sets.append(f"{field} = %s")
            params.append(val)

    sets.append("updated_at = NOW()")

    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(offer_id)
    row = db.execute_returning(
        f"""
        UPDATE offers
        SET {', '.join(sets)}
        WHERE id = %s
        RETURNING *
        """,
        params,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row), 200


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

@bp.route("/api/offers/<int:offer_id>/benchmark", methods=["POST"])
def benchmark_offer(offer_id):
    """Compare offer against salary benchmarks + COLA adjustment."""
    offer = db.query_one(
        """
        SELECT o.*, a.role, a.company_name
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id = %s
        """,
        (offer_id,),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    # Find best-matching benchmark by role
    role_title = offer.get("title_offered") or offer.get("role") or ""
    benchmarks = db.query("SELECT * FROM salary_benchmarks ORDER BY sort_order")

    best_match = None
    for b in benchmarks:
        if b["role_title"].lower() in role_title.lower() or role_title.lower() in b["role_title"].lower():
            best_match = b
            break
    if not best_match and benchmarks:
        best_match = benchmarks[0]

    # COLA adjustment for offer location
    offer_location = (offer.get("location") or "").lower()
    cola = db.query_one(
        "SELECT * FROM cola_markets WHERE LOWER(market_name) LIKE %s LIMIT 1",
        (f"%{offer_location.split(',')[0].strip()}%" if offer_location else "%melbourne%",),
    )
    if not cola:
        cola = db.query_one(
            "SELECT * FROM cola_markets WHERE LOWER(market_name) LIKE %s LIMIT 1",
            ("%melbourne%",),
        )

    offer_base = float(offer.get("base_salary") or 0)
    cola_factor = float(cola["cola_factor"]) if cola else 1.0

    # Parse benchmark range (format: "$X - $Y" or "$X-$Y")
    def parse_range(range_str):
        if not range_str:
            return None, None
        cleaned = range_str.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000")
        parts = cleaned.split("-")
        try:
            low = float(parts[0].strip())
            high = float(parts[1].strip()) if len(parts) > 1 else low
            return low, high
        except (ValueError, IndexError):
            return None, None

    melbourne_range = best_match.get("melbourne_range") if best_match else None
    national_range = best_match.get("national_median_range") if best_match else None
    bm_low, bm_high = parse_range(melbourne_range or national_range)

    cola_adjusted_base = offer_base * cola_factor if cola_factor != 1.0 else offer_base

    # Percentile estimate
    percentile = None
    if bm_low and bm_high and offer_base > 0:
        if offer_base <= bm_low:
            percentile = 25
        elif offer_base >= bm_high:
            percentile = 90
        else:
            percentile = 25 + 65 * ((offer_base - bm_low) / (bm_high - bm_low))
            percentile = round(percentile)

    analysis = []
    if percentile is not None:
        if percentile < 40:
            analysis.append("Offer is below market median. Strong grounds for negotiation.")
        elif percentile < 60:
            analysis.append("Offer is at market median. Room to negotiate toward upper quartile.")
        elif percentile < 80:
            analysis.append("Offer is above median, competitive range.")
        else:
            analysis.append("Offer is in the top quartile. Very competitive.")

    if cola_factor != 1.0:
        analysis.append(
            f"COLA adjustment factor for {cola.get('market_name', 'location')}: {cola_factor}x. "
            f"Melbourne-equivalent base: ${cola_adjusted_base:,.0f}."
        )

    return jsonify({
        "offer_id": offer_id,
        "offer_base": offer_base,
        "benchmark_role": best_match["role_title"] if best_match else None,
        "benchmark_range": melbourne_range or national_range,
        "cola_market": cola.get("market_name") if cola else None,
        "cola_factor": cola_factor,
        "cola_adjusted_base": round(cola_adjusted_base, 2),
        "percentile_estimate": percentile,
        "analysis": analysis,
    }), 200


# ---------------------------------------------------------------------------
# Total Comp
# ---------------------------------------------------------------------------

def _calc_total_comp(offer):
    """Calculate year-by-year total comp for an offer dict."""
    base = float(offer.get("base_salary") or 0)
    bonus_target = float(offer.get("annual_bonus_target") or 0)
    if not bonus_target and offer.get("annual_bonus_pct"):
        bonus_target = base * float(offer["annual_bonus_pct"]) / 100.0
    signing = float(offer.get("signing_bonus") or 0)
    equity_total = float(offer.get("equity_value") or 0)
    vesting_months = int(offer.get("equity_vesting_months") or 48)
    cliff_months = int(offer.get("equity_cliff_months") or 12)

    # Calculate equity per year with cliff
    years = max(1, vesting_months // 12)
    equity_per_year = equity_total / years if years > 0 else 0

    breakdown = []
    four_year_total = 0
    for y in range(1, 5):
        month_start = (y - 1) * 12
        month_end = y * 12

        # Equity vests after cliff
        if month_end <= cliff_months:
            eq = 0  # still in cliff
        elif month_start < cliff_months <= month_end:
            # Cliff vests this year: get backpay for cliff period
            cliff_years = cliff_months / 12.0
            eq = equity_per_year * cliff_years
        else:
            eq = equity_per_year if month_start < vesting_months else 0

        year_bonus = bonus_target
        year_signing = signing if y == 1 else 0
        year_total = base + year_bonus + eq + year_signing

        breakdown.append({
            "year": y,
            "base": round(base, 2),
            "bonus": round(year_bonus, 2),
            "signing_bonus": round(year_signing, 2),
            "equity_vested": round(eq, 2),
            "total": round(year_total, 2),
        })
        four_year_total += year_total

    return breakdown, round(four_year_total, 2)


@bp.route("/api/offers/<int:offer_id>/total-comp", methods=["POST"])
def total_comp(offer_id):
    """Calculate total compensation with year-by-year breakdown."""
    offer = db.query_one(
        """
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id = %s
        """,
        (offer_id,),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    breakdown, four_year_total = _calc_total_comp(offer)

    return jsonify({
        "offer_id": offer_id,
        "company": offer.get("company_name"),
        "role": offer.get("title_offered") or offer.get("role"),
        "annual_breakdown": breakdown,
        "four_year_total": four_year_total,
    }), 200


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

@bp.route("/api/offers/compare", methods=["POST"])
def compare_offers():
    """Compare multiple offers side by side.

    Body: { offer_ids: [int] }
    """
    data = request.get_json(force=True)
    offer_ids = data.get("offer_ids")
    if not offer_ids or not isinstance(offer_ids, list) or len(offer_ids) < 2:
        return jsonify({"error": "offer_ids array with at least 2 IDs is required"}), 400

    placeholders = ",".join(["%s"] * len(offer_ids))
    offers = db.query(
        f"""
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id IN ({placeholders})
        ORDER BY o.base_salary DESC NULLS LAST
        """,
        offer_ids,
    )

    if len(offers) < 2:
        return jsonify({"error": "Need at least 2 valid offers to compare"}), 400

    comparisons = []
    for offer in offers:
        breakdown, four_year_total = _calc_total_comp(offer)
        comparisons.append({
            "offer_id": offer["id"],
            "company": offer.get("company_name"),
            "role": offer.get("title_offered") or offer.get("role"),
            "base_salary": float(offer.get("base_salary") or 0),
            "signing_bonus": float(offer.get("signing_bonus") or 0),
            "annual_bonus_target": float(offer.get("annual_bonus_target") or 0),
            "equity_value": float(offer.get("equity_value") or 0),
            "equity_type": offer.get("equity_type"),
            "remote_policy": offer.get("remote_policy"),
            "pto_days": offer.get("pto_days"),
            "location": offer.get("location"),
            "four_year_total": four_year_total,
            "year_1_total": breakdown[0]["total"] if breakdown else 0,
            "decision_factors": offer.get("decision_factors"),
            "status": offer.get("status"),
        })

    # Sort by 4-year total desc
    comparisons.sort(key=lambda x: x["four_year_total"], reverse=True)

    # Add rank and delta from top
    top_total = comparisons[0]["four_year_total"]
    for i, c in enumerate(comparisons):
        c["rank"] = i + 1
        c["delta_from_top"] = round(c["four_year_total"] - top_total, 2)

    return jsonify({"comparisons": comparisons, "count": len(comparisons)}), 200


# ---------------------------------------------------------------------------
# Counter-Offer
# ---------------------------------------------------------------------------

@bp.route("/api/offers/<int:offer_id>/counter", methods=["POST"])
def create_counter(offer_id):
    """Create a counter-offer version.

    Body: modified offer fields for the counter.
    """
    original = db.query_one("SELECT * FROM offers WHERE id = %s", (offer_id,))
    if not original:
        return jsonify({"error": "Offer not found"}), 404

    data = request.get_json(force=True)
    new_version = (original.get("version") or 1) + 1

    row = db.execute_returning(
        """
        INSERT INTO offers
            (application_id, version, version_label, base_salary, signing_bonus,
             annual_bonus_pct, annual_bonus_target, equity_type, equity_value,
             equity_shares, equity_vesting_months, equity_cliff_months,
             benefits_notes, pto_days, remote_policy, title_offered,
             start_date, expiration_date, location, status,
             negotiation_notes, decision_factors)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            original["application_id"],
            new_version,
            data.get("version_label", "counter"),
            data.get("base_salary", original.get("base_salary")),
            data.get("signing_bonus", original.get("signing_bonus")),
            data.get("annual_bonus_pct", original.get("annual_bonus_pct")),
            data.get("annual_bonus_target", original.get("annual_bonus_target")),
            data.get("equity_type", original.get("equity_type")),
            data.get("equity_value", original.get("equity_value")),
            data.get("equity_shares", original.get("equity_shares")),
            data.get("equity_vesting_months", original.get("equity_vesting_months")),
            data.get("equity_cliff_months", original.get("equity_cliff_months")),
            data.get("benefits_notes", original.get("benefits_notes")),
            data.get("pto_days", original.get("pto_days")),
            data.get("remote_policy", original.get("remote_policy")),
            data.get("title_offered", original.get("title_offered")),
            data.get("start_date", original.get("start_date")),
            data.get("expiration_date", original.get("expiration_date")),
            data.get("location", original.get("location")),
            "negotiating",
            data.get("negotiation_notes"),
            json.dumps(data["decision_factors"]) if data.get("decision_factors") else None,
        ),
    )

    # Mark original as negotiating
    db.execute(
        "UPDATE offers SET status = 'negotiating', updated_at = NOW() WHERE id = %s",
        (offer_id,),
    )

    return jsonify(row), 201


# ---------------------------------------------------------------------------
# Scenario Modeling
# ---------------------------------------------------------------------------

@bp.route("/api/offers/<int:offer_id>/scenario", methods=["POST"])
def scenario_model(offer_id):
    """Run scenario modeling on an offer.

    Body: { scenarios: [{label, base, bonus_pct, equity_value, signing_bonus}] }
    """
    offer = db.query_one("SELECT * FROM offers WHERE id = %s", (offer_id,))
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    data = request.get_json(force=True)
    scenarios = data.get("scenarios")
    if not scenarios or not isinstance(scenarios, list):
        return jsonify({"error": "scenarios array is required"}), 400

    results = []
    for s in scenarios:
        sim = dict(offer)
        if "base" in s or "base_salary" in s:
            sim["base_salary"] = s.get("base") or s.get("base_salary")
        if "bonus_pct" in s or "annual_bonus_pct" in s:
            sim["annual_bonus_pct"] = s.get("bonus_pct") or s.get("annual_bonus_pct")
            sim["annual_bonus_target"] = None  # recalc from pct
        if "equity_value" in s:
            sim["equity_value"] = s["equity_value"]
        if "signing_bonus" in s:
            sim["signing_bonus"] = s["signing_bonus"]

        breakdown, four_year_total = _calc_total_comp(sim)
        results.append({
            "label": s.get("label", "Unnamed"),
            "base_salary": float(sim.get("base_salary") or 0),
            "annual_breakdown": breakdown,
            "four_year_total": four_year_total,
        })

    # Sort by 4-year total desc and add deltas
    results.sort(key=lambda x: x["four_year_total"], reverse=True)
    top = results[0]["four_year_total"] if results else 0
    for i, r in enumerate(results):
        r["rank"] = i + 1
        r["delta_from_top"] = round(r["four_year_total"] - top, 2)

    return jsonify({"offer_id": offer_id, "scenarios": results}), 200


# ---------------------------------------------------------------------------
# Accept / Decline
# ---------------------------------------------------------------------------

@bp.route("/api/offers/<int:offer_id>/accept", methods=["POST"])
def accept_offer(offer_id):
    """Accept an offer. Updates offer and application status."""
    offer = db.execute_returning(
        """
        UPDATE offers SET status = 'accepted', updated_at = NOW()
        WHERE id = %s RETURNING *
        """,
        (offer_id,),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    db.execute(
        "UPDATE applications SET status = 'Accepted', last_status_change = NOW() WHERE id = %s",
        (offer["application_id"],),
    )

    return jsonify({"offer": offer, "message": "Offer accepted. Application status updated."}), 200


@bp.route("/api/offers/<int:offer_id>/decline", methods=["POST"])
def decline_offer(offer_id):
    """Decline an offer. Updates offer status; updates application if no other accepted offer."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason")

    notes_update = f"Declined: {reason}" if reason else "Declined"
    offer = db.execute_returning(
        """
        UPDATE offers
        SET status = 'declined', negotiation_notes = COALESCE(negotiation_notes || E'\\n', '') || %s,
            updated_at = NOW()
        WHERE id = %s RETURNING *
        """,
        (notes_update, offer_id),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    # Only update application to Declined if no other accepted offer exists
    accepted = db.query_one(
        "SELECT id FROM offers WHERE application_id = %s AND status = 'accepted' AND id != %s",
        (offer["application_id"], offer_id),
    )
    if not accepted:
        db.execute(
            "UPDATE applications SET status = 'Declined', last_status_change = NOW() WHERE id = %s",
            (offer["application_id"],),
        )

    return jsonify({"offer": offer, "message": "Offer declined."}), 200


# ---------------------------------------------------------------------------
# Email Generation
# ---------------------------------------------------------------------------

@bp.route("/api/offers/<int:offer_id>/acceptance-email", methods=["POST"])
def acceptance_email(offer_id):
    """Generate an acceptance email and store in generated_materials."""
    offer = db.query_one(
        """
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id = %s
        """,
        (offer_id,),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    company = offer.get("company_name", "[Company]")
    role = offer.get("title_offered") or offer.get("role", "[Role]")
    start = offer.get("start_date")
    start_str = start.strftime("%B %d, %Y") if start else "[start date]"

    content = (
        f"Dear Hiring Team,\n\n"
        f"I am thrilled to formally accept the {role} position at {company}. "
        f"Thank you for this opportunity... I am excited to contribute to the team.\n\n"
        f"As discussed, I will plan to start on {start_str}. "
        f"Please let me know if there is any paperwork or onboarding steps "
        f"I should complete before my start date.\n\n"
        f"Looking forward to getting started.\n\n"
        f"Best regards,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, company_name, role_title,
             content, content_format, voice_check_passed, generation_context, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            "acceptance_email",
            offer["application_id"],
            company,
            role,
            content,
            "text",
            False,
            json.dumps({"offer_id": offer_id}),
            "draft",
        ),
    )
    return jsonify(row), 201


@bp.route("/api/offers/<int:offer_id>/decline-email", methods=["POST"])
def decline_email(offer_id):
    """Generate a gracious decline email and store in generated_materials."""
    offer = db.query_one(
        """
        SELECT o.*, a.company_name, a.role
        FROM offers o
        JOIN applications a ON o.application_id = a.id
        WHERE o.id = %s
        """,
        (offer_id,),
    )
    if not offer:
        return jsonify({"error": "Offer not found"}), 404

    header = db.query_one("SELECT full_name FROM resume_header ORDER BY id LIMIT 1")
    candidate_name = header["full_name"] if header else "Candidate"

    company = offer.get("company_name", "[Company]")
    role = offer.get("title_offered") or offer.get("role", "[Role]")

    content = (
        f"Dear Hiring Team,\n\n"
        f"Thank you so much for offering me the {role} position at {company}. "
        f"I truly appreciate the time and consideration throughout the process.\n\n"
        f"After careful deliberation, I have decided to pursue another opportunity "
        f"that more closely aligns with my current career goals. "
        f"This was not an easy decision... the team and mission at {company} are impressive.\n\n"
        f"I hope our paths cross again in the future and wish the team continued success.\n\n"
        f"Warm regards,\n{candidate_name}"
    )

    row = db.execute_returning(
        """
        INSERT INTO generated_materials
            (type, application_id, company_name, role_title,
             content, content_format, voice_check_passed, generation_context, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            "decline_email",
            offer["application_id"],
            company,
            role,
            content,
            "text",
            False,
            json.dumps({"offer_id": offer_id}),
            "draft",
        ),
    )
    return jsonify(row), 201
