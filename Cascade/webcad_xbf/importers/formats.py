SUPPORTED_FORMATS = {

    # Native CascadeCAD
    ".xbf": {
        "category": "NATIVE",
        "handler": "xbf_importer"
    },

    # CAD solids
    ".step": {
        "category": "SOLID",
        "handler": "step_importer"
    },
    ".stp": {
        "category": "SOLID",
        "handler": "step_importer"
    },
    ".iges": {
        "category": "SOLID",
        "handler": "iges_importer"
    },
    ".igs": {
        "category": "SOLID",
        "handler": "iges_importer"
    },
    ".brep": {
        "category": "SOLID",
        "handler": "brep_importer"
    },
    ".fcstd": {
        "category": "SOLID",
        "handler": "freecad_importer"
    },
    ".x_t": {
        "category": "SOLID",
        "handler": "parasolid_importer"
    },
    ".x_b": {
        "category": "SOLID",
        "handler": "parasolid_importer"
    },

    # Mesh formats
    ".stl": {
        "category": "MESH",
        "handler": "mesh_importer"
    },
    ".obj": {
        "category": "MESH",
        "handler": "mesh_importer"
    },
    ".ply": {
        "category": "MESH",
        "handler": "mesh_importer"
    },
    ".off": {
        "category": "MESH",
        "handler": "mesh_importer"
    },
    ".3mf": {
        "category": "MESH",
        "handler": "mesh_importer"
    },

    # Web / interchange
    ".glb": {
        "category": "MESH",
        "handler": "glb_importer"
    },
    ".gltf": {
        "category": "MESH",
        "handler": "glb_importer"
    },
}


def get_format(filename):
    filename = filename.lower()

    for ext, info in SUPPORTED_FORMATS.items():
        if filename.endswith(ext):
            return {
                "extension": ext,
                **info
            }

    return {
        "extension": None,
        "category": "UNKNOWN",
        "handler": None
    }
