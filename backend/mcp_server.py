"""SuperTroopers MCP Server — exposes DB tools for Claude Code.

Run:  python mcp_server.py   # starts MCP server on stdio

This file is the import-and-register hub only.
All tool implementations live in mcp_tools_*.py satellites.
"""

import sys
import os

# Ensure the backend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
import db

mcp = FastMCP(
    "supertroopers",
    instructions="SuperTroopers hiring platform database tools.",
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", 8056)),
)


# ---------------------------------------------------------------------------
# Register all tool groups from satellites
# ---------------------------------------------------------------------------

from mcp_tools_knowledge import register_knowledge_tools
register_knowledge_tools(mcp)

from mcp_tools_pipeline import register_pipeline_tools
register_pipeline_tools(mcp)

from mcp_tools_contacts import register_contacts_tools
register_contacts_tools(mcp)

from mcp_tools_resume_gen import register_resume_gen_tools
register_resume_gen_tools(mcp)

from mcp_tools_notifications import register_notifications_tools
register_notifications_tools(mcp)

from mcp_tools_fresh_jobs import register_fresh_jobs_tools
register_fresh_jobs_tools(mcp)

from mcp_tools_aging import register_aging_tools
register_aging_tools(mcp)

from mcp_tools_crm import register_crm_tools
register_crm_tools(mcp)

from mcp_tools_workflows import register_workflows_tools
register_workflows_tools(mcp)

from mcp_tools_market_intel import register_market_intel_tools
register_market_intel_tools(mcp)

from mcp_tools_networking import register_networking_tools
register_networking_tools(mcp)

from mcp_tools_search_intel import register_search_intel_tools
register_search_intel_tools(mcp)

from mcp_tools_skills_dev import register_skills_dev_tools
register_skills_dev_tools(mcp)


# ---------------------------------------------------------------------------
# Delegate stubs for satellites that expose raw functions (no register_ yet)
# ---------------------------------------------------------------------------

# Mock Interviews
@mcp.tool()
def create_mock_interview(
    job_title: str,
    company: str,
    interview_type: str = "behavioral",
    difficulty: str = "medium",
    application_id: int | None = None,
) -> dict:
    """Create a mock interview session with generated questions.

    Args:
        job_title: Job title to tailor questions for
        company: Target company name
        interview_type: behavioral, technical, situational, case, or mixed
        difficulty: easy, medium, or hard
        application_id: Optional linked application ID
    """
    from mcp_tools_mock_interviews import create_mock_interview as _impl
    return _impl(job_title, company, interview_type, difficulty, application_id)


@mcp.tool()
def get_mock_interview(interview_id: int) -> dict:
    """Get a mock interview session with all questions and scores.

    Args:
        interview_id: ID of the mock interview to retrieve
    """
    from mcp_tools_mock_interviews import get_mock_interview as _impl
    return _impl(interview_id)


@mcp.tool()
def evaluate_mock_interview(interview_id: int, answers: dict) -> dict:
    """Evaluate answers for a mock interview and generate scores/feedback.

    Args:
        interview_id: ID of the mock interview
        answers: Dict mapping question_id to answer text, e.g. {"1": "My answer..."}
    """
    from mcp_tools_mock_interviews import evaluate_mock_interview as _impl
    return _impl(interview_id, answers)


# LinkedIn Profile & Brand
@mcp.tool()
def run_profile_audit(audit_type: str = "full", target_jd_ids: list | None = None) -> dict:
    """Create a LinkedIn profile audit record with section scores and recommendations.

    Args:
        audit_type: full, headline, about, experience, skills, featured
        target_jd_ids: optional list of saved_job IDs for match scoring
    """
    from mcp_tools_linkedin import run_profile_audit as _impl
    return _impl(audit_type, target_jd_ids)


@mcp.tool()
def generate_headline_variants(target_role: str | None = None, count: int = 3) -> dict:
    """Generate LinkedIn headline variant suggestions using candidate profile data.

    Args:
        target_role: optional target role to optimize headlines for
        count: number of variants to generate (default 3)
    """
    from mcp_tools_linkedin import generate_headline_variants as _impl
    return _impl(target_role, count)


@mcp.tool()
def generate_linkedin_post(topic: str, theme_pillar_id: int | None = None, style: str = "text") -> dict:
    """Create a draft LinkedIn post record.

    Args:
        topic: the topic or idea for the post
        theme_pillar_id: optional theme pillar ID to associate with
        style: post type — text, article, poll, carousel, video, document
    """
    from mcp_tools_linkedin import generate_linkedin_post as _impl
    return _impl(topic, theme_pillar_id, style)


@mcp.tool()
def check_linkedin_voice(text: str) -> dict:
    """Validate text against LinkedIn voice rules. Returns violations and suggestions.

    Args:
        text: the text to check against active LinkedIn voice rules
    """
    from mcp_tools_linkedin import check_linkedin_voice as _impl
    return _impl(text)


@mcp.tool()
def run_skills_audit(target_jd_ids: list | None = None) -> dict:
    """Create a LinkedIn skills audit comparing DB skills to target JDs.

    Args:
        target_jd_ids: optional list of saved_job IDs to compare against
    """
    from mcp_tools_linkedin import run_skills_audit as _impl
    return _impl(target_jd_ids)


@mcp.tool()
def get_linkedin_analytics(days: int = 30) -> dict:
    """Return LinkedIn content performance analytics over specified period.

    Args:
        days: lookback window in days (default 30)
    """
    from mcp_tools_linkedin import get_linkedin_analytics as _impl
    return _impl(days)


@mcp.tool()
def get_linkedin_profile_scorecard() -> dict:
    """Return the latest profile audit as a scorecard summary with section grades and top recommendations."""
    from mcp_tools_linkedin import get_linkedin_profile_scorecard as _impl
    return _impl()


# Application Materials Generation
@mcp.tool()
def generate_cover_letter(
    application_id: int | None = None,
    saved_job_id: int | None = None,
    company_name: str | None = None,
    role_title: str | None = None,
) -> dict:
    """Generate a cover letter using gap analysis, company dossier, and career bullets.

    Args:
        application_id: optional application ID (pulls gap analysis + company)
        saved_job_id: optional saved job ID
        company_name: target company name
        role_title: target role title
    """
    from mcp_tools_materials import generate_cover_letter as _impl
    return _impl(application_id, saved_job_id, company_name, role_title)


@mcp.tool()
def generate_thank_you(
    application_id: int,
    interviewer_name: str | None = None,
    interview_notes: str | None = None,
) -> dict:
    """Generate a post-interview thank-you note. Under 200 words, references debrief data.

    Args:
        application_id: the application ID (pulls interview/debrief context)
        interviewer_name: optional interviewer name to personalize
        interview_notes: optional notes about the interview discussion
    """
    from mcp_tools_materials import generate_thank_you as _impl
    return _impl(application_id, interviewer_name, interview_notes)


@mcp.tool()
def generate_outreach(
    contact_id: int,
    message_type: str = "networking",
    channel: str = "email",
    application_id: int | None = None,
) -> dict:
    """Generate a personalized outreach message to a contact. Under 150 words.

    Args:
        contact_id: the contact to reach out to
        message_type: cold_outreach, warm_intro_request, follow_up, thank_you, networking, recruiter
        channel: email, linkedin, phone
        application_id: optional application for context
    """
    from mcp_tools_materials import generate_outreach as _impl
    return _impl(contact_id, message_type, channel, application_id)


@mcp.tool()
def batch_outreach(
    contact_ids: list,
    message_type: str = "networking",
    application_id: int | None = None,
) -> dict:
    """Generate personalized outreach for multiple contacts. Each message is individually personalized.

    Args:
        contact_ids: list of contact IDs
        message_type: message type for all messages
        application_id: optional application for context
    """
    from mcp_tools_materials import batch_outreach as _impl
    return _impl(contact_ids, message_type, application_id)


# Advanced Resume & Gap Analysis
@mcp.tool()
def generate_resume_variant(
    role_type: str,
    application_id: int | None = None,
    saved_job_id: int | None = None,
) -> dict:
    """Generate a role-tailored resume variant (CTO, VP Eng, Director, etc.).

    Args:
        role_type: target role type (CTO, VP Eng, Director, AI Architect, SW Architect, PM, Sr SWE)
        application_id: optional application for context
        saved_job_id: optional saved job for context
    """
    from mcp_tools_resume_tailoring import generate_resume_variant as _impl
    return _impl(role_type, application_id, saved_job_id)


@mcp.tool()
def run_ats_score(
    jd_text: str,
    resume_text: str | None = None,
    application_id: int | None = None,
) -> dict:
    """Score a resume against a JD for ATS compatibility.

    Args:
        jd_text: job description text to score against
        resume_text: optional resume text (if omitted, pulls latest generated material)
        application_id: optional application ID to pull resume from
    """
    from mcp_tools_resume_tailoring import run_ats_score as _impl
    return _impl(jd_text, resume_text, application_id)


@mcp.tool()
def run_gap_analysis(
    jd_text: str | None = None,
    saved_job_id: int | None = None,
    application_id: int | None = None,
) -> dict:
    """Run a simplified gap analysis matching JD keywords against skills and bullets.

    Args:
        jd_text: job description text (or pulled from saved_job)
        saved_job_id: optional saved job to pull JD from
        application_id: optional application to link results to
    """
    from mcp_tools_resume_tailoring import run_gap_analysis as _impl
    return _impl(jd_text, saved_job_id, application_id)


# Offer Evaluation & Negotiation
@mcp.tool()
def log_offer(
    application_id: int,
    base_salary: float | None = None,
    signing_bonus: float | None = None,
    annual_bonus_pct: float | None = None,
    equity_type: str | None = None,
    equity_value: float | None = None,
    equity_vesting_months: int = 48,
    equity_cliff_months: int = 12,
    pto_days: int | None = None,
    remote_policy: str | None = None,
    title_offered: str | None = None,
    start_date: str | None = None,
    location: str | None = None,
    benefits_notes: str | None = None,
) -> dict:
    """Log a new job offer linked to an application.

    Args:
        application_id: application this offer belongs to (required)
        base_salary: annual base salary
        signing_bonus: one-time signing bonus
        annual_bonus_pct: annual bonus as percentage of base
        equity_type: rsu, options, or none
        equity_value: total equity grant value
        equity_vesting_months: vesting period in months (default 48)
        equity_cliff_months: cliff period in months (default 12)
        pto_days: paid time off days per year
        remote_policy: remote, hybrid, or onsite
        title_offered: job title in the offer
        start_date: proposed start date (YYYY-MM-DD)
        location: work location
        benefits_notes: freeform benefits description
    """
    from mcp_tools_offers import log_offer as _impl
    return _impl(
        application_id, base_salary, signing_bonus, annual_bonus_pct,
        equity_type, equity_value, equity_vesting_months, equity_cliff_months,
        pto_days, remote_policy, title_offered, start_date, location, benefits_notes,
    )


@mcp.tool()
def total_comp(offer_id: int) -> dict:
    """Calculate total compensation for an offer over 4 years.

    Args:
        offer_id: the offer to calculate total comp for
    """
    from mcp_tools_offers import total_comp as _impl
    return _impl(offer_id)


@mcp.tool()
def compare_offers(offer_ids: list) -> dict:
    """Compare multiple offers side by side with total comp analysis.

    Args:
        offer_ids: list of offer IDs to compare
    """
    from mcp_tools_offers import compare_offers as _impl
    return _impl(offer_ids)


@mcp.tool()
def benchmark_offer(offer_id: int) -> dict:
    """Compare an offer against salary benchmarks with COLA adjustment.

    Args:
        offer_id: the offer to benchmark
    """
    from mcp_tools_offers import benchmark_offer as _impl
    return _impl(offer_id)


# Reference Management
@mcp.tool()
def get_reference_roster() -> dict:
    """List all references with warmth status, usage stats, and role type matching."""
    from mcp_tools_references import get_reference_roster as _impl
    return _impl()


@mcp.tool()
def match_references_to_role(role_type: str) -> dict:
    """Match references to a specific role type, ranked by fit and warmth.

    Args:
        role_type: target role (CTO, VP Eng, Director, AI Architect, etc.)
    """
    from mcp_tools_references import match_references_to_role as _impl
    return _impl(role_type)


@mcp.tool()
def check_reference_warmth() -> dict:
    """Check which references need a check-in (>90 days since last contact)."""
    from mcp_tools_references import check_reference_warmth as _impl
    return _impl()


@mcp.tool()
def log_reference_use(contact_id: int, application_id: int) -> dict:
    """Log that a reference was used for an application.

    Args:
        contact_id: the reference contact
        application_id: the application they were used for
    """
    from mcp_tools_references import log_reference_use as _impl
    return _impl(contact_id, application_id)


# Campaign & Onboarding
@mcp.tool()
def convert_saved_job(saved_job_id: int) -> dict:
    """Convert a saved job into an application record.

    Args:
        saved_job_id: the saved job to convert
    """
    from mcp_tools_campaign import convert_saved_job as _impl
    return _impl(saved_job_id)


@mcp.tool()
def close_out_campaign(accepted_application_id: int) -> dict:
    """Execute campaign close-out: accept one offer, withdraw all others, generate emails.

    Args:
        accepted_application_id: the application with the accepted offer
    """
    from mcp_tools_campaign import close_out_campaign as _impl
    return _impl(accepted_application_id)


@mcp.tool()
def get_campaign_summary() -> dict:
    """Get campaign analytics summary: total apps, response rates, offer rates, timeline, sources."""
    from mcp_tools_campaign import get_campaign_summary as _impl
    return _impl()


# Analytics & Reporting
@mcp.tool()
def get_pipeline_report() -> dict:
    """Get pipeline funnel report with conversion rates and time-in-stage analysis."""
    from mcp_tools_reporting import get_pipeline_report as _impl
    return _impl()


@mcp.tool()
def get_campaign_report() -> dict:
    """Get full campaign performance dashboard: stats, best companies, weekly heatmap."""
    from mcp_tools_reporting import get_campaign_report as _impl
    return _impl()


@mcp.tool()
def get_interview_analytics() -> dict:
    """Get comprehensive interview analytics: win rates by type, common question themes,
    feeling distribution, STAR category performance, prep effectiveness score,
    improvement themes extracted from debriefs, win rate by company size, and recent trend."""
    from mcp_tools_reporting import get_interview_analytics as _impl
    return _impl()


@mcp.tool()
def get_weekly_rollup() -> dict:
    """Get weekly rollup: this week vs last week with deltas for all key metrics."""
    from mcp_tools_reporting import get_weekly_rollup as _impl
    return _impl()


@mcp.tool()
def get_weekly_digest() -> dict:
    """Get full weekly campaign digest: rollup metrics, pipeline trends, and strategy recommendations.

    Combines get_weekly_rollup + get_pipeline_report + strategy recommendations into one call.
    Recommendations include: application volume guidance, follow-up cadence triggers,
    interview skill alerts, networking nudges, and positive momentum signals.
    """
    from mcp_tools_reporting import (
        get_weekly_rollup as _rollup,
        get_pipeline_report as _pipeline,
        generate_strategy_recommendations as _recs,
    )
    rollup = _rollup()
    pipeline = _pipeline()
    recommendations = _recs(rollup, pipeline)
    return {
        "rollup": rollup,
        "pipeline": pipeline,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sse", action="store_true", help="Run as SSE server (for Docker)")
    parser.add_argument("--port", type=int, default=8056, help="SSE server port")
    args = parser.parse_args()

    if args.sse:
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
