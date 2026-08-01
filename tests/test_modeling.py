import pytest

from webcad_xbf.geometry import _parameter_number, _parameter_vector


def test_model_parameter_validation():
    assert _parameter_number({"radius": 25}, "radius", 1) == 25
    assert _parameter_vector({"position": [1, 2, 3]}) == (1.0, 2.0, 3.0)
    with pytest.raises(ValueError):
        _parameter_number({"radius": -1}, "radius", 1)
