"""Google Workspace, Gemini GenContent, and Mail Admin OAuth Trigger services for Genmunity OpsAgent."""
from .google_workspace import GoogleWorkspaceService, get_workspace_service
from .mail_trigger import (
    DEFAULT_ADMIN_EMAIL,
    load_admin_registry,
    save_admin_registry,
    sync_live_gmail_profile,
    register_mail_admin_via_oauth,
    check_and_trigger_on_inbound_emails,
)

from .event_hub import (
    UPLOADS_DIR,
    list_events,
    get_event_by_id,
    create_or_modify_event,
    manage_event_rsvp,
    add_event_knowledge_entry,
    analyze_event_photo_and_track_attendees,
    search_all_event_knowledge,
)

__all__ = [
    "GoogleWorkspaceService",
    "get_workspace_service",
    "DEFAULT_ADMIN_EMAIL",
    "load_admin_registry",
    "save_admin_registry",
    "sync_live_gmail_profile",
    "register_mail_admin_via_oauth",
    "check_and_trigger_on_inbound_emails",
    "UPLOADS_DIR",
    "list_events",
    "get_event_by_id",
    "create_or_modify_event",
    "manage_event_rsvp",
    "add_event_knowledge_entry",
    "analyze_event_photo_and_track_attendees",
    "search_all_event_knowledge",
]
