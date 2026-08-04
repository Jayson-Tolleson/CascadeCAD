from __future__ import annotations

import asyncio
import time
from pathlib import Path

from PIL import Image, ImageOps


def normalize_share_image(source: Path, destination: Path) -> None:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
        square = Image.new("RGB", (1080, 1080), "white")
        left = (1080 - image.width) // 2
        top = (1080 - image.height) // 2
        square.paste(image, (left, top))
        # Keep the image under the conservative social upload ceiling while
        # removing EXIF and all other source metadata.
        for quality in (90, 86, 82, 78, 72):
            square.save(destination, format="JPEG", quality=quality, optimize=True, progressive=True)
            if destination.stat().st_size <= 1_900_000:
                break


def cleanup_share_media(directory: Path, *, max_age_seconds: int = 24 * 3600) -> None:
    cutoff = time.time() - max_age_seconds
    for path in directory.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


async def normalize_share_video(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-t",
        "60",
        "-vf",
        "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2",
        "-r",
        "30",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=180)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError("FFmpeg timed out while preparing the 60-second social video")
    if process.returncode != 0 or not destination.exists() or destination.stat().st_size == 0:
        detail = stderr.decode("utf-8", "replace").strip()[-2000:]
        raise RuntimeError(f"FFmpeg could not prepare the social video: {detail or 'unknown error'}")
