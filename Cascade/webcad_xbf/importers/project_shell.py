from pathlib import Path
import uuid
from datetime import datetime

from ..xbf_document import XBFDocument


def create_xbf_shell(source_file, import_info, storage_dir):

    project_id = "prj_" + uuid.uuid4().hex[:12]

    project_dir = Path(storage_dir) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    xbf_file = project_dir / "document.xbf"

    #
    # Create real CascadeCAD XBF
    #
    doc = XBFDocument(project_id)

    asset_id = doc.import_cad_file(
        str(Path(storage_dir) / source_file)
    )

    doc.metadata.update({
        "project_id": project_id,
        "created": datetime.utcnow().isoformat(),
        "source": source_file,
        "import": import_info
    })

    doc.save(str(xbf_file))


    return {
        "project_id": project_id,
        "project_path": str(project_dir),
        "xbf": str(xbf_file),
        "asset_id": asset_id,
        "manifest": {
            "project_id": project_id,
            "created": doc.metadata["created"],
            "source": source_file,
            "format": import_info,
            "status": "READY",
            "native_format": "XBF"
        }
    }
