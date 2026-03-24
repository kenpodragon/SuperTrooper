"""MCP tool functions for Offer Evaluation & Negotiation.

Standalone functions — orchestrator wires these into mcp_server.py.
"""

import json
import db
from ai_providers.router import route_inference


def log_offer(application_id: int, base_salary: float = None, signing_bonus: float = None,
              annual_bonus_pct: float = None, annual_bonus_target: float = None,
              equity_type: str = None, equity_value: float = None,
              equity_shares: int = None, equity_vesting_months: int = 48,
              equity_cliff_months: int = 12, benefits_notes: str = None,
              pto_days: int = None, remote_policy: str = None,
              title_offered: str = None, start_date: str = None,
              expiration_date: str = None, location: str = None,
              negotiation_notes: str = None):
    """Log a new offer for an application.

    Args:
        application_id: ID of the application this offer is for (required)
        base_salary: Annual base salary
        signing_bonus: One-time signing bonus
        annual_bonus_pct: Annual bonus as percentage of base
        annual_bonus_target: Annual bonus dollar amount
        equity_type: rsu, options, or none
        equity_value: Total grant value in dollars
        equity_shares: Number of shares
        equity_vesting_months: Total vesting period (default 48)
        equity_cliff_months: Cliff period (default 12)
        benefits_notes: Freeform benefits description
        pto_days: PTO days per year
        remote_policy: remote, hybrid, or onsite
        title_offered: Job title in the offer
        start_date: Proposed start date (YYYY-MM-DD)
        expiration_date: Offer expiration date (YYYY-MM-DD)
        location: Work location
        negotiation_notes: Any negotiation context
    """
    app = db.query_one("SELECT id FROM applications WHERE id = %s", (application_id,))
    if not app:
        return {"error": f"Application {application_id} not found"}

    row = db.execute_returning(
        """
        INSERT INTO offers
            (application_id, version, version_label, base_salary, signing_bonus,
             annual_bonus_pct, annual_bonus_target, equity_type, equity_value,
             equity_shares, equity_vesting_months, equity_cliff_months,
             benefits_notes, pto_days, remote_policy, title_offered,
             start_date, expiration_date, location, status, negotiation_notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            application_id, 1, "initial", base_salary, signing_bonus,
            annual_bonus_pct, annual_bonus_target, equity_type, equity_value,
            equity_shares, equity_vesting_months, equity_cliff_months,
            benefits_notes, pto_days, remote_policy, title_offered,
            start_date, expiration_date, location, "pending", negotiation_notes,
        ),
    )
    return row


def total_comp(offer_id: int):
    """Calculate total compensation for an offer with year-by-year breakdown.

    Args:
        offer_id: ID of the offer to calculate
    """
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
        return {"error": f"Offer {offer_id} not found"}

    base = float(offer.get("base_salary") or 0)
    bonus_target = float(offer.get("annual_bonus_target") or 0)
    if not bonus_target and offer.get("annual_bonus_pct"):
        bonus_target = base * float(offer["annual_bonus_pct"]) / 100.0
    signing = float(offer.get("signing_bonus") or 0)
    equity_total = float(offer.get("equity_value") or 0)
    vesting_months = int(offer.get("equity_vesting_months") or 48)
    cliff_months = int(offer.get("equity_cliff_months") or 12)
    years = max(1, vesting_months // 12)
    equity_per_year = equity_total / years if years > 0 else 0

    breakdown = []
    four_year_total = 0
    for y in range(1, 5):
        month_start = (y - 1) * 12
        month_end = y * 12
        if month_end <= cliff_months:
            eq = 0
        elif month_start < cliff_months <= month_end:
            eq = equity_per_year * (cliff_months / 12.0)
        else:
            eq = equity_per_year if month_start < vesting_months else 0

        year_signing = signing if y == 1 else 0
        year_total = base + bonus_target + eq + year_signing
        breakdown.append({
            "year": y, "base": round(base, 2), "bonus": round(bonus_target, 2),
            "signing_bonus": round(year_signing, 2), "equity_vested": round(eq, 2),
            "total": round(year_total, 2),
        })
        four_year_total += year_total

    return {
        "offer_id": offer_id,
        "company": offer.get("company_name"),
        "role": offer.get("title_offered") or offer.get("role"),
        "annual_breakdown": breakdown,
        "four_year_total": round(four_year_total, 2),
    }


def compare_offers(offer_ids: list):
    """Compare multiple offers side by side.

    Args:
        offer_ids: List of offer IDs to compare (minimum 2)
    """
    if not offer_ids or len(offer_ids) < 2:
        return {"error": "At least 2 offer IDs required"}

    results = []
    for oid in offer_ids:
        comp = total_comp(oid)
        if "error" in comp:
            continue
        offer = db.query_one("SELECT * FROM offers WHERE id = %s", (oid,))
        results.append({
            "offer_id": oid,
            "company": comp["company"],
            "role": comp["role"],
            "base_salary": float(offer.get("base_salary") or 0),
            "equity_value": float(offer.get("equity_value") or 0),
            "remote_policy": offer.get("remote_policy"),
            "pto_days": offer.get("pto_days"),
            "location": offer.get("location"),
            "four_year_total": comp["four_year_total"],
            "year_1_total": comp["annual_breakdown"][0]["total"],
        })

    results.sort(key=lambda x: x["four_year_total"], reverse=True)
    top = results[0]["four_year_total"] if results else 0
    for i, r in enumerate(results):
        r["rank"] = i + 1
        r["delta_from_top"] = round(r["four_year_total"] - top, 2)

    python_result = {"comparisons": results, "count": len(results)}

    def _python_compare(ctx):
        return ctx["r"]

    def _ai_compare(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        offers_data = [{
            "company": r["company"], "role": r["role"],
            "base": r["base_salary"], "four_year": r["four_year_total"],
            "remote": r.get("remote_policy"), "pto": r.get("pto_days"),
        } for r in ctx["r"]["comparisons"]]
        result = provider.compare_offers(offers_data)
        base = ctx["r"]
        base["ai_trade_offs"] = result.get("trade_offs", [])
        base["ai_recommendation"] = result.get("recommendation", "")
        return base

    return route_inference(
        task="compare_offers",
        context={"r": python_result},
        python_fallback=_python_compare,
        ai_handler=_ai_compare,
    )


def benchmark_offer(offer_id: int):
    """Compare an offer against salary benchmarks with COLA adjustment.

    Args:
        offer_id: ID of the offer to benchmark
    """
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
        return {"error": f"Offer {offer_id} not found"}

    role_title = offer.get("title_offered") or offer.get("role") or ""
    benchmarks = db.query("SELECT * FROM salary_benchmarks ORDER BY sort_order")

    best_match = None
    for b in benchmarks:
        if b["role_title"].lower() in role_title.lower() or role_title.lower() in b["role_title"].lower():
            best_match = b
            break
    if not best_match and benchmarks:
        best_match = benchmarks[0]

    offer_location = (offer.get("location") or "").lower()
    cola = db.query_one(
        "SELECT * FROM cola_markets WHERE LOWER(market_name) LIKE %s LIMIT 1",
        (f"%{offer_location.split(',')[0].strip()}%" if offer_location else "%melbourne%",),
    )
    if not cola:
        cola = db.query_one("SELECT * FROM cola_markets WHERE LOWER(market_name) LIKE %s LIMIT 1", ("%melbourne%",))

    offer_base = float(offer.get("base_salary") or 0)
    cola_factor = float(cola["cola_factor"]) if cola else 1.0
    cola_adjusted = offer_base * cola_factor

    python_result = {
        "offer_id": offer_id,
        "offer_base": offer_base,
        "benchmark_role": best_match["role_title"] if best_match else None,
        "benchmark_range": (best_match.get("melbourne_range") or best_match.get("national_median_range")) if best_match else None,
        "cola_market": cola.get("market_name") if cola else None,
        "cola_factor": cola_factor,
        "cola_adjusted_base": round(cola_adjusted, 2),
    }

    def _python_bench(ctx):
        return ctx["r"]

    def _ai_bench(ctx):
        from ai_providers import get_provider
        provider = get_provider()
        offer_data = {"base_salary": ctx["r"]["offer_base"], "role": ctx["r"]["benchmark_role"],
                      "location": ctx["r"].get("cola_market")}
        salary_data = {"range": ctx["r"].get("benchmark_range"), "cola_factor": ctx["r"]["cola_factor"]}
        result = provider.benchmark_offer(offer_data, salary_data)
        base = ctx["r"]
        base["ai_assessment"] = result.get("assessment", "")
        base["ai_negotiation_points"] = result.get("negotiation_points", [])
        base["ai_counter_suggestion"] = result.get("counter_suggestion", {})
        return base

    return route_inference(
        task="benchmark_offer",
        context={"r": python_result},
        python_fallback=_python_bench,
        ai_handler=_ai_bench,
    )
