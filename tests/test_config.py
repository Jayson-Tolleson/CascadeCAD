from webcad_xbf.config import _base_path


def test_base_path():
    assert _base_path('/cascade-cad/') == '/cascade-cad'
    assert _base_path('/') == ''
    assert _base_path('') == ''
