from pathlib import Path
import json
import uuid
from datetime import datetime


def create_xbf_shell(source_file, import_info, storage_dir):
    project_id = "prj_" + uuid.uuid4().hex[:12]

    project_dir = Path(storage_dir) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    xbf_file = project_dir / "document.xbf"

    manifest = {
        "project_id": project_id,
        "created": datetime.utcnow().isoformat(),
        "source": source_file,
        "format": import_info,
        "status": "IMPORT_PENDING",
        "native_format": "XBF"
    }

    xbf_file.write_text(
        json.dumps(manifest, indent=2)
    )

    return {
        "project_id": project_id,
        "project_path": str(project_dir),
        "xbf": str(xbf_file),
        "manifest": manifest
    }

