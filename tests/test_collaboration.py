from pathlib import Path

import pytest

from webcad_xbf.collaboration import CollaborationStore


def test_uuid_sessions_presence_and_conservative_project_labels(tmp_path: Path):
    store = CollaborationStore(tmp_path)
    first = store.create_or_resume_session(
        username="Jayson",
        status="available",
        project_visibility="hidden",
        project_category="Marine CAD",
    )
    second = store.create_or_resume_session(
        username="Alex User",
        status="busy",
        project_visibility="category",
        project_category="Mechanical CAD",
    )

    jayson = store.authenticate(first["session_token"])
    alex = store.authenticate(second["session_token"])
    assert jayson["id"].startswith("usr_")
    assert alex["id"].startswith("usr_")

    store.touch_presence(
        jayson["id"],
        project_id="prj_12345678",
        project_name="Confidential Boat",
        project_visibility="hidden",
    )
    store.touch_presence(
        alex["id"],
        project_id="prj_87654321",
        project_name="Visible Test Rig",
        project_visibility="category",
        project_category="Mechanical CAD",
    )

    rows = {row["username"]: row for row in store.active_users(store.authenticate(first["session_token"]))}
    assert rows["Jayson"]["project_label"] == "Private project"
    assert rows["Jayson"]["project_id"] is None
    assert rows["Alex User"]["project_label"] == "Mechanical CAD"
    assert rows["Alex User"]["project_id"] is None


def test_private_project_chat_invites_direct_messages_and_global_moderation(tmp_path: Path):
    store = CollaborationStore(tmp_path)
    first = store.create_or_resume_session(username="Owner User")
    second = store.create_or_resume_session(username="Editor User")
    owner = store.authenticate(first["session_token"])
    editor = store.authenticate(second["session_token"])
    project_id = "prj_12345678"

    claimed = store.join_or_claim_project(project_id, owner)
    assert claimed["membership"]["role"] == "owner"
    with pytest.raises(PermissionError):
        store.join_or_claim_project(project_id, editor)

    invited = store.invite_project_user(project_id, owner, "Editor User", "editor")
    assert {row["role"] for row in invited["members"]} == {"owner", "editor"}
    assert store.join_or_claim_project(project_id, editor)["membership"]["role"] == "editor"

    project_message = store.post_project(project_id, owner, "Check this selected frame", ["cmp_12345678"])
    assert project_message["component_ids"] == ["cmp_12345678"]
    assert store.project_messages(project_id, editor)[0]["text"] == "Check this selected frame"

    direct_message = store.post_direct(editor, owner["id"], "I am reviewing it")
    assert direct_message["recipient_user_id"] == owner["id"]
    assert store.direct_messages(owner, editor["id"])[0]["text"] == "I am reviewing it"

    global_message = store.post_global(owner, "CascadeCAD community update")
    report = store.report_message(editor, global_message["id"], "Test moderation report")
    assert report["id"].startswith("rpt_")

    store.block_user(editor, owner["id"], True)
    refreshed_editor = store.authenticate(second["session_token"])
    assert owner["id"] in refreshed_editor["blocked_user_ids"]
    assert store.global_messages(refreshed_editor) == []
    with pytest.raises(PermissionError):
        store.post_direct(refreshed_editor, owner["id"], "blocked")
