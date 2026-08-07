from .detect import detect_file


IMPORT_HANDLERS = {
    "step_importer": "STEP importer",
    "iges_importer": "IGES importer",
    "brep_importer": "BREP importer",
    "freecad_importer": "FreeCAD importer",
    "parasolid_importer": "Parasolid importer",
    "mesh_importer": "Mesh importer",
    "glb_importer": "GLB importer",
    "xbf_importer": "Native XBF loader",
}


def route_import(filename):

    result = detect_file(filename)

    if not result["supported"]:
        return {
            **result,
            "status": "REJECTED"
        }

    return {
        **result,
        "status": "READY",
        "target": IMPORT_HANDLERS.get(
            result["handler"],
            "UNKNOWN"
        )
    }


if __name__ == "__main__":
    import sys

    for filename in sys.argv[1:]:
        print(route_import(filename))
