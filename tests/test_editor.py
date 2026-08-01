from webcad_xbf.editor import apply_operation, component_list, new_state, redo, state_summary, undo


def sample_components():
    return [
        {
            "id": "cab",
            "name": "Cab",
            "kind": "exact",
            "editable": True,
            "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0]},
        }
    ]


def test_transform_undo_redo():
    state = new_state(sample_components())
    apply_operation(
        state,
        {
            "operation": "transform",
            "component_id": "cab",
            "transform": {"position": [10, 20, 30], "rotation": [0, 0, 90]},
        },
    )
    assert state["components"]["cab"]["transform"]["position"] == [10.0, 20.0, 30.0]
    assert state_summary(state)["dirty"] is True
    undo(state)
    assert state["components"]["cab"]["transform"]["position"] == [0.0, 0.0, 0.0]
    redo(state)
    assert state["components"]["cab"]["transform"]["rotation"] == [0.0, 0.0, 90.0]


def test_duplicate_and_delete():
    state = new_state(sample_components())
    apply_operation(state, {"operation": "duplicate", "component_id": "cab", "offset": 50})
    duplicates = [c for c in component_list(state) if c["duplicate"]]
    assert len(duplicates) == 1
    assert duplicates[0]["source_id"] == "cab"
    assert duplicates[0]["transform"]["position"][0] == 50.0
    apply_operation(state, {"operation": "delete", "component_id": "cab"})
    assert state["components"]["cab"]["deleted"] is True


def test_scale_material_visibility_and_rename_are_persistent():
    state = new_state(sample_components())
    apply_operation(state, {
        "operation": "transform", "component_id": "cab",
        "transform": {"position": [25.4, 0, 0], "rotation": [1, 2, 3], "scale": [1.25, 0.5, 2]},
    })
    apply_operation(state, {
        "operation": "material", "component_id": "cab",
        "material": {"name": "Steel", "density_kg_m3": 7850, "color": "#7f8992"},
    })
    apply_operation(state, {"operation": "visibility", "component_id": "cab", "visible": False})
    apply_operation(state, {"operation": "rename", "component_id": "cab", "name": "Cab frame"})
    record = state["components"]["cab"]
    assert record["transform"]["scale"] == [1.25, 0.5, 2.0]
    assert record["material"]["density_kg_m3"] == 7850.0
    assert record["material"]["color"] == "#7f8992"
    assert record["visible"] is False
    assert record["name"] == "Cab frame"
