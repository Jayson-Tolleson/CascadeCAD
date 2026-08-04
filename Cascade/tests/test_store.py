from pathlib import Path

from webcad_xbf.store import Store


def test_chunked_upload(tmp_path: Path):
    store = Store(tmp_path)
    project = store.create_project("Truck", "truck.step")
    upload = store.create_upload(project["id"], "truck.step", 6)

    first = store.append_chunk(upload["id"], 0, b"abc")
    assert first["received"] == 3

    # Retrying a successfully stored chunk must be idempotent.
    duplicate = store.append_chunk(upload["id"], 0, b"abc")
    assert duplicate["received"] == 3

    second = store.append_chunk(upload["id"], 3, b"def")
    assert second["received"] == 6

    metadata, target = store.finish_upload(upload["id"])
    assert metadata["complete"] is True
    assert target.read_bytes() == b"abcdef"

    # Retrying finish after a lost response must return the existing target.
    metadata_again, target_again = store.finish_upload(upload["id"])
    assert metadata_again["complete"] is True
    assert target_again == target
    assert target_again.read_bytes() == b"abcdef"


def test_project_delete_and_active_job_protection(tmp_path: Path):
    store = Store(tmp_path)
    project = store.create_project("Frame", "frame.xbf")
    store.update_project(project["id"], status="processing")
    try:
        store.delete_project(project["id"])
    except ValueError as exc:
        assert "active upload or geometry job" in str(exc)
    else:
        raise AssertionError("active project deletion should be rejected")

    store.update_project(project["id"], status="ready")
    job = store.create_job("export_step", project["id"], {})
    store.update_job(job["id"], status="complete")
    store.delete_project(project["id"])
    assert not store.project_dir(project["id"]).exists()
    assert not (store.jobs / f"{job['id']}.json").exists()


def test_upload_preserves_mesh_cleanup_option(tmp_path: Path):
    store = Store(tmp_path)
    project = store.create_project("Mesh", "mesh.3mf", import_options={"mesh_cleanup": True})
    upload = store.create_upload(project["id"], "mesh.3mf", 3, options={"mesh_cleanup": True})
    assert project["import_options"]["mesh_cleanup"] is True
    assert upload["options"]["mesh_cleanup"] is True
