from webcad_xbf.geometry import _combined_geometry_kind, _unique_subassembly_name


class FakeAssembly:
    def __init__(self, names=()):
        self.objects = {name: object() for name in names}


def test_combined_geometry_kind():
    assert _combined_geometry_kind(["exact", "exact"]) == "exact"
    assert _combined_geometry_kind(["mesh", "mesh"]) == "mesh"
    assert _combined_geometry_kind(["exact", "mesh"]) == "mixed"
    assert _combined_geometry_kind(["unknown", "exact"]) == "unknown"


def test_unique_subassembly_name():
    assembly = FakeAssembly({"project_cab", "project_cab_2"})
    assert _unique_subassembly_name(assembly, "project cab") == "project_cab_3"
