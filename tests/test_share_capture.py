from pathlib import Path

from PIL import Image

from webcad_xbf.share_media import normalize_share_image


def test_square_capture_share_is_wired():
    root = Path(__file__).resolve().parents[1]
    template = (root / "webcad_xbf" / "templates" / "project.html").read_text()
    project_js = (root / "webcad_xbf" / "static" / "js" / "project.js").read_text()
    share_js = (root / "webcad_xbf" / "static" / "js" / "share-capture.js").read_text()
    app = (root / "webcad_xbf" / "app.py").read_text()
    share_media = (root / "webcad_xbf" / "share_media.py").read_text()
    installer = (root / "install.sh").read_text()

    for token in (
        "share-draw-square",
        "share-photo",
        "share-record",
        "share-stop",
        "share-bluesky",
        "share-instagram",
        "share-dialog",
    ):
        assert token in template
    assert "initShareCapture" in project_js
    assert "preserveDrawingBuffer: false" in project_js
    assert "renderer.render(scene, camera)" in project_js
    for token in (
        "captureStream",
        "MAX_RECORDING_SECONDS = 60",
        "navigator.canShare",
        "bsky.app/intent/compose",
        "www.instagram.com",
        "/share-media/normalize",
    ):
        assert token in share_js
    for token in ("normalize_share_video", '"video/mp4"', "share-media/<filename>"):
        assert token in app
    for token in ("libx264", "yuv420p", '"60"'):
        assert token in share_media
    assert "ffmpeg" in installer


def test_share_image_normalization_is_square_and_metadata_free(tmp_path):
    source = tmp_path / "source.png"
    destination = tmp_path / "normalized.jpg"
    image = Image.new("RGB", (640, 360), (30, 120, 220))
    exif = image.getexif()
    exif[0x010E] = "private source description"
    image.save(source, exif=exif)

    normalize_share_image(source, destination)

    assert destination.stat().st_size <= 1_900_000
    with Image.open(destination) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.size == (1080, 1080)
        assert len(normalized.getexif()) == 0
