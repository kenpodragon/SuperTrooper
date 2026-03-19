"""Configuration loaded from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5555"))
DB_NAME = os.getenv("DB_NAME", "supertroopers")
DB_USER = os.getenv("DB_USER", "supertroopers")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

FLASK_PORT = int(os.getenv("FLASK_PORT", "8055"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
