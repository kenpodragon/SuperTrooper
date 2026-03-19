"""Route blueprints for the SuperTroopers Flask API."""

from routes.career import bp as career_bp
from routes.pipeline import bp as pipeline_bp
from routes.contacts import bp as contacts_bp
from routes.content import bp as content_bp
from routes.analytics import bp as analytics_bp
from routes.search import bp as search_bp
from routes.knowledge import bp as knowledge_bp
from routes.resume import bp as resume_bp

ALL_BLUEPRINTS = [
    career_bp,
    pipeline_bp,
    contacts_bp,
    content_bp,
    analytics_bp,
    search_bp,
    knowledge_bp,
    resume_bp,
]
