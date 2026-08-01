from pathlib import Path


def test_frontend_has_no_inline_runtime_config():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'webcad_xbf/templates/index.html').read_text()
    project = (root / 'webcad_xbf/templates/project.html').read_text()
    assert 'window.CASCADE_CAD_CONFIG' not in index
    assert 'window.CASCADE_CAD_CONFIG' not in project
    assert 'data-base-path=' in index
    assert 'data-base-path=' in project


def test_nginx_separates_uploads_and_websockets():
    root = Path(__file__).resolve().parents[1]
    nginx = (root / 'deploy/nginx/cascade-cad-location.conf').read_text()
    assert 'location ^~ /cascade-cad/ws/' in nginx
    assert 'location ^~ /cascade-cad/' in nginx
    assert 'proxy_set_header Connection "";' in nginx
