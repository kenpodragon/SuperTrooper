"""
Google OAuth flow for Google Workspace MCP integration.

Endpoints:
  POST /api/integrations/google/credentials  — Save credentials.json from user
  POST /api/integrations/google/auth-url     — Generate OAuth authorization URL
  POST /api/integrations/google/exchange      — Exchange auth code for token
  DELETE /api/integrations/google/credentials — Remove stored credentials + token
"""

import json
import logging
from flask import Blueprint, request, jsonify
import db

log = logging.getLogger(__name__)
bp = Blueprint("google_oauth", __name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/contacts.readonly",
]


def _get_integrations():
    row = db.query_one("SELECT integrations FROM settings WHERE id = 1")
    cfg = (row.get("integrations") or {}) if row else {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    return cfg


def _save_integrations(cfg):
    db.execute(
        "UPDATE settings SET integrations = %s::jsonb, updated_at = NOW() WHERE id = 1",
        (json.dumps(cfg),),
    )


@bp.route("/api/integrations/google/credentials", methods=["POST"])
def save_credentials():
    """Save Google OAuth credentials.json content.

    Body: the raw contents of credentials.json (paste from Google Cloud Console).
    Accepts either the full file or just the 'installed' or 'web' object inside it.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    # Handle different formats: full file vs inner object
    if "installed" in data:
        client_config = data["installed"]
        config_type = "installed"
    elif "web" in data:
        client_config = data["web"]
        config_type = "web"
    elif "client_id" in data and "client_secret" in data:
        client_config = data
        config_type = "installed"
    else:
        return jsonify({
            "error": "Invalid credentials format. Expected Google OAuth credentials.json with 'installed' or 'web' key, or an object with client_id and client_secret.",
        }), 400

    # Validate required fields
    required = ["client_id", "client_secret"]
    missing = [f for f in required if not client_config.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    # Store in integrations JSONB
    cfg = _get_integrations()
    google = cfg.get("google", {})
    google["credentials"] = {config_type: client_config}
    google["credentials_stored"] = True
    cfg["google"] = google
    _save_integrations(cfg)

    return jsonify({
        "status": "saved",
        "client_id": client_config["client_id"][:20] + "...",
        "config_type": config_type,
    }), 200


@bp.route("/api/integrations/google/auth-url", methods=["POST"])
def get_auth_url():
    """Generate Google OAuth authorization URL.

    User visits this URL, authorizes, and gets a code to paste back.
    """
    cfg = _get_integrations()
    google = cfg.get("google", {})
    creds = google.get("credentials")

    if not creds:
        return jsonify({"error": "No credentials stored. Save credentials.json first."}), 400

    # Extract client config
    config_type = "installed" if "installed" in creds else "web"
    client_config = creds[config_type]
    client_id = client_config["client_id"]

    # For desktop apps, use urn:ietf:wg:oauth:2.0:oob or localhost redirect
    redirect_uri = client_config.get("redirect_uris", ["urn:ietf:wg:oauth:2.0:oob"])[0]
    # Prefer localhost redirect if available, fall back to manual copy
    for uri in client_config.get("redirect_uris", []):
        if "localhost" in uri:
            redirect_uri = uri
            break

    # Use out-of-band for desktop apps (user copies code manually)
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    scopes_str = " ".join(SCOPES)

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scopes_str}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

    return jsonify({
        "auth_url": auth_url,
        "redirect_uri": redirect_uri,
        "scopes": SCOPES,
        "instructions": "Open this URL in your browser, authorize access, then copy the authorization code and paste it back.",
    }), 200


@bp.route("/api/integrations/google/exchange", methods=["POST"])
def exchange_code():
    """Exchange authorization code for OAuth token.

    Body: {"code": "4/0Abc..."}
    """
    data = request.get_json(force=True)
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Authorization code is required"}), 400

    cfg = _get_integrations()
    google = cfg.get("google", {})
    creds = google.get("credentials")

    if not creds:
        return jsonify({"error": "No credentials stored. Save credentials.json first."}), 400

    config_type = "installed" if "installed" in creds else "web"
    client_config = creds[config_type]

    # Exchange code for token using requests (no google-auth dependency needed)
    import requests as http_requests
    try:
        token_resp = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_config["client_id"],
                "client_secret": client_config["client_secret"],
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "grant_type": "authorization_code",
            },
            timeout=15,
        )

        if token_resp.status_code != 200:
            error_data = token_resp.json() if token_resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({
                "error": "Token exchange failed",
                "details": error_data.get("error_description", token_resp.text[:200]),
            }), 400

        token_data = token_resp.json()

        # Store token in DB
        google["token"] = token_data
        google["token_stored"] = True
        google["enabled"] = True
        cfg["google"] = google
        _save_integrations(cfg)

        return jsonify({
            "status": "authorized",
            "token_type": token_data.get("token_type"),
            "scopes": token_data.get("scope", "").split(" "),
            "expires_in": token_data.get("expires_in"),
        }), 200

    except http_requests.RequestException as e:
        return jsonify({"error": f"Token exchange request failed: {str(e)}"}), 500


@bp.route("/api/integrations/google/credentials", methods=["DELETE"])
def delete_credentials():
    """Remove stored Google OAuth credentials and token."""
    cfg = _get_integrations()
    google = cfg.get("google", {})
    google.pop("credentials", None)
    google.pop("token", None)
    google["credentials_stored"] = False
    google["token_stored"] = False
    google["enabled"] = False
    cfg["google"] = google
    _save_integrations(cfg)

    return jsonify({"status": "removed"}), 200
