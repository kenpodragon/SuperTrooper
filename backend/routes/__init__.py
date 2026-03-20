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
]
