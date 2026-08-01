from pathlib import Path


def test_collaboration_ui_and_routes_are_packaged():
    root = Path(__file__).resolve().parents[1]
    template = (root / "webcad_xbf/templates/project.html").read_text()
    browser = (root / "webcad_xbf/static/js/collaboration.js").read_text()
    backend = (root / "webcad_xbf/collaboration.py").read_text()
    app = (root / "webcad_xbf/app.py").read_text()

    for token in (
        "collaboration-users-button", "project-chat-button", "community-button",
        "project-members-list", "global-user-list", "project-chat-messages",
        "Global Broadcast Board", "collaboration-profile-dialog", "direct-message-list",
    ):
        assert token in template
    for token in (
        "SESSION_KEY", "connectGlobalSocket", "connectProjectSocket", "openDirectConversation",
        "project_visibility", "component_ids", "reportMessage", "blockUser",
    ):
        assert token in browser
    for token in (
        "CollaborationStore", "join_or_claim_project", "invite_project_user", "post_global",
        "post_project", "post_direct", "report_message", "block_user", "Slow mode",
        "/api/collaboration/global/messages", "/ws/collaboration/global",
    ):
        assert token in backend
    assert "register_collaboration_routes" in app
    assert '"global_broadcast_board": True' in app
