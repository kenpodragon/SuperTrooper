"""SuperTroopers Flask API — entry point.

Run:  python app.py          # starts Flask on port 8055
"""

import json
import sys
import os

# Ensure the backend directory is on sys.path so relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_cors import CORS

import config
import db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.json.default = db.serialize  # handle dates, decimals in JSON

    # CORS — allow everything on localhost (single-user, local only)
    CORS(app, resources={r"/api/*": {"origins": "*", "expose_headers": ["Content-Disposition"]}})

    # Register blueprints
    from routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Health check
    @app.route("/api/health", methods=["GET"])
    def health():
        try:
            row = db.query_one("SELECT 1 AS ok")
            return {"status": "healthy", "db": "connected"}, 200
        except Exception as e:
            return {"status": "unhealthy", "db": str(e)}, 503

    # Teardown — not strictly needed with pool, but good practice
    @app.teardown_appcontext
    def shutdown_pool(exception=None):
        pass  # pool stays alive for the process lifetime

    return app


if __name__ == "__main__":
    import argparse
    import threading

    parser = argparse.ArgumentParser(description="SuperTroopers Backend")
    parser.add_argument("--no-mcp", action="store_true", help="Skip MCP server")
    parser.add_argument("--mcp-port", type=int, default=8056, help="MCP SSE port")
    args = parser.parse_args()

    app = create_app()

    # Start MCP server in background thread (SSE transport)
    if not args.no_mcp:
        def run_mcp():
            from mcp_server import mcp as mcp_instance
            print(f"SuperTroopers MCP starting on http://localhost:{args.mcp_port}")
            mcp_instance.settings.host = "0.0.0.0"
            mcp_instance.settings.port = args.mcp_port
            mcp_instance.run(transport="sse")

        mcp_thread = threading.Thread(target=run_mcp, daemon=True)
        mcp_thread.start()

    print(f"SuperTroopers API starting on http://localhost:{config.FLASK_PORT}")
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=config.FLASK_DEBUG)
