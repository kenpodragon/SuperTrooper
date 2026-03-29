"""Route blueprints for the SuperTroopers Flask API."""

from routes.career import bp as career_bp
from routes.pipeline import bp as pipeline_bp
from routes.contacts import bp as contacts_bp
from routes.content import bp as content_bp
from routes.analytics import bp as analytics_bp
from routes.search import bp as search_bp
from routes.knowledge import bp as knowledge_bp
from routes.resume import bp as resume_bp
from routes.saved_jobs import bp as saved_jobs_bp
from routes.gap_analysis import bp as gap_analysis_bp
from routes.interview_extras import bp as interview_extras_bp
from routes.activity import bp as activity_bp
from routes.settings import bp as settings_bp
from routes.onboard import bp as onboard_bp
from routes.notifications import bp as notifications_bp
from routes.fresh_jobs import bp as fresh_jobs_bp
from routes.aging import bp as aging_bp
from routes.crm import bp as crm_bp
from routes.workflows import bp as workflows_bp
from routes.market_intelligence import bp as market_intelligence_bp
from routes.batch import bp as batch_bp
from routes.mock_interviews import bp as mock_interviews_bp
from routes.integrations import bp as integrations_bp
from routes.linkedin import bp as linkedin_bp
from routes.materials import bp as materials_bp
from routes.resume_tailoring import bp as resume_tailoring_bp
from routes.offers import bp as offers_bp
from routes.search_intelligence import bp as search_intelligence_bp
from routes.references import bp as references_bp
from routes.skills_development import bp as skills_development_bp
from routes.campaign import bp as campaign_bp
from routes.path_finding import bp as path_finding_bp
from routes.linkedin_import import bp as linkedin_import_bp
from routes.reporting import bp as reporting_bp
from routes.market_intelligence_fetch import bp as market_intelligence_fetch_bp
from routes.email_intelligence import bp as email_intelligence_bp
from routes.calendar_intelligence import bp as calendar_intelligence_bp
from routes.profile import bp as profile_bp
from routes.jd_fetch import bp as jd_fetch_bp
from routes.google_oauth import bp as google_oauth_bp
from routes.bullet_ops import bp as bullet_ops_bp
from routes.kb_dedup import bp as kb_dedup_bp

ALL_BLUEPRINTS = [
    career_bp,
    pipeline_bp,
    contacts_bp,
    content_bp,
    analytics_bp,
    search_bp,
    knowledge_bp,
    resume_bp,
    saved_jobs_bp,
    gap_analysis_bp,
    interview_extras_bp,
    activity_bp,
    settings_bp,
    onboard_bp,
    notifications_bp,
    fresh_jobs_bp,
    aging_bp,
    crm_bp,
    workflows_bp,
    market_intelligence_bp,
    batch_bp,
    mock_interviews_bp,
    integrations_bp,
    linkedin_bp,
    materials_bp,
    resume_tailoring_bp,
    offers_bp,
    search_intelligence_bp,
    references_bp,
    skills_development_bp,
    campaign_bp,
    path_finding_bp,
    linkedin_import_bp,
    reporting_bp,
    market_intelligence_fetch_bp,
    email_intelligence_bp,
    calendar_intelligence_bp,
    profile_bp,
    jd_fetch_bp,
    google_oauth_bp,
    bullet_ops_bp,
    kb_dedup_bp,
]
