"""
MCP tools for Google Workspace (Gmail, Calendar, Drive).

Credentials loaded from DB — no files, no subprocess.
These tools are available to AI agents via the SuperTroopers MCP server.
"""

from integrations import google_client


def register_google_tools(mcp):
    """Register Google Workspace MCP tools."""

    # --- Gmail ---

    @mcp.tool()
    def google_gmail_search(query: str, max_results: int = 10) -> dict:
        """Search Gmail messages. Returns matching emails with sender, subject, date, snippet.

        Args:
            query: Gmail search query (same syntax as Gmail search bar). Examples: "from:recruiter", "subject:interview", "is:unread".
            max_results: Maximum number of messages to return (default 10, max 100).
        """
        return google_client.gmail_search(query, max_results)

    @mcp.tool()
    def google_gmail_read(message_id: str) -> dict:
        """Read a specific Gmail message with full body text.

        Args:
            message_id: Gmail message ID (from search results).
        """
        return google_client.gmail_read(message_id)

    @mcp.tool()
    def google_gmail_draft(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
        """Create a Gmail draft (does NOT send). Use for outreach, follow-ups, thank-you notes.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body text.
            cc: CC recipients (comma-separated).
            bcc: BCC recipients (comma-separated).
        """
        return google_client.gmail_draft(to, subject, body, cc, bcc)

    @mcp.tool()
    def google_gmail_send(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
        """Send an email via Gmail. Use with caution — this actually sends.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body text.
            cc: CC recipients (comma-separated).
            bcc: BCC recipients (comma-separated).
        """
        return google_client.gmail_send(to, subject, body, cc, bcc)

    # --- Calendar ---

    @mcp.tool()
    def google_calendar_list(days: int = 14, max_results: int = 50) -> dict:
        """List upcoming Google Calendar events. Useful for detecting interviews.

        Args:
            days: Number of days ahead to look (default 14).
            max_results: Maximum events to return (default 50).
        """
        return google_client.gcal_list_events(days, max_results=max_results)

    @mcp.tool()
    def google_calendar_create(
        summary: str, start_time: str, end_time: str,
        description: str = "", location: str = "",
    ) -> dict:
        """Create a Google Calendar event.

        Args:
            summary: Event title.
            start_time: Start time in RFC3339 format (e.g., "2026-03-25T10:00:00-04:00").
            end_time: End time in RFC3339 format.
            description: Optional event description.
            location: Optional event location.
        """
        return google_client.gcal_create_event(summary, start_time, end_time, description, location)

    # --- Drive ---

    @mcp.tool()
    def google_drive_list(query: str = "", max_results: int = 20) -> dict:
        """List or search Google Drive files.

        Args:
            query: Drive search query. Examples: "name contains 'resume'", "mimeType='application/pdf'". Empty returns recent files.
            max_results: Maximum files to return (default 20).
        """
        return google_client.gdrive_list(query, max_results)

    @mcp.tool()
    def google_drive_upload(file_path: str, name: str = "", folder_id: str = "") -> dict:
        """Upload a file to Google Drive. Useful for pushing generated resumes.

        Args:
            file_path: Local path to the file to upload.
            name: Name for the file in Drive (defaults to local filename).
            folder_id: Optional Drive folder ID to upload into.
        """
        return google_client.gdrive_upload(file_path, name, folder_id)

    # --- Health ---

    @mcp.tool()
    def google_health() -> dict:
        """Check Google Workspace connection status. Returns email address if connected."""
        return google_client.health_check()
