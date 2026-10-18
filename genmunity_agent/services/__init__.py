"""Google Workspace, Gemini GenContent, and Mail Admin OAuth Trigger services for Genmunity OpsAgent."""
from .google_workspace import GoogleWorkspaceService, get_workspace_service
from .mail_trigger import (
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_GCP_PROJECT,
    DEFAULT_PUBSUB_TOPIC,
    DEFAULT_PUBSUB_SUBSCRIPTION,
    load_admin_registry,
    save_admin_registry,
    sync_live_gmail_profile,
    register_mail_admin_via_oauth,
    check_and_trigger_on_inbound_emails,
    evaluate_and_handle_inbound_inquiry,
    decode_pubsub_push_payload,
)

from .email_templates import render_genmunity_email_html
from .event_hub import (
    UPLOADS_DIR,
    list_events,
    get_event_by_id,
    create_or_modify_event,
    save_event_wysiwyg_content,
    generate_event_image_with_gemini,
    manage_event_rsvp,
    add_event_knowledge_entry,
    analyze_event_photo_and_track_attendees,
    search_all_event_knowledge,
    sync_speaker_form_submission_to_event_state,
    get_main_event_readiness_summary,
)
from .collaboration_proposal import (
    audit_collaboration_links,
    send_speaker_collaboration_proposal_emails,
)

__all__ = [
    "GoogleWorkspaceService",
    "get_workspace_service",
    "render_genmunity_email_html",
    "DEFAULT_ADMIN_EMAIL",
    "DEFAULT_GCP_PROJECT",
    "DEFAULT_PUBSUB_TOPIC",
    "DEFAULT_PUBSUB_SUBSCRIPTION",
    "load_admin_registry",
    "save_admin_registry",
    "sync_live_gmail_profile",
    "register_mail_admin_via_oauth",
    "check_and_trigger_on_inbound_emails",
    "evaluate_and_handle_inbound_inquiry",
    "decode_pubsub_push_payload",
    "UPLOADS_DIR",
    "list_events",
    "get_event_by_id",
    "create_or_modify_event",
    "save_event_wysiwyg_content",
    "generate_event_image_with_gemini",
    "manage_event_rsvp",
    "add_event_knowledge_entry",
    "analyze_event_photo_and_track_attendees",
    "search_all_event_knowledge",
    "sync_speaker_form_submission_to_event_state",
    "get_main_event_readiness_summary",
    "audit_collaboration_links",
    "send_speaker_collaboration_proposal_emails",
]

