import json
from pathlib import Path

class ProjectManager:
    SUBDIRECTORIES = [
        "xbf", "imports", "assemblies", "drawings", 
        "exports", "textures", "cache", "autosave", "backups"
    ]

    @classmethod
    def create_project(cls, root_path: str, project_name: str) -> Path:
        base_dir = Path(root_path) / project_name
        base_dir.mkdir(parents=True, exist_ok=True)

        for sub in cls.SUBDIRECTORIES:
            (base_dir / sub).mkdir(exist_ok=True)

        manifest_path = base_dir / f"{project_name}.ccproj"
        manifest_data = {
            "schema_version": "1.0.0",
            "project_name": project_name,
            "units": "millimeters",
            "settings": {
                "autosave_interval_sec": 300,
                "render_quality": "high"
            },
            "assets": {
                "imports": [],
                "xbf_files": [],
                "drawings": []
            }
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return manifest_path

    @staticmethod
    def load_project(manifest_path: str) -> dict:
        path = Path(manifest_path)
        if not path.exists():
            raise FileNotFoundError(f"Project manifest not found: {manifest_path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_project(manifest_path: str, data: dict):
        path = Path(manifest_path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
