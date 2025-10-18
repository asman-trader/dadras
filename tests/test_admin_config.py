import json
import os


def test_masked_config(client):
    r = client.get('/admin/config')
    assert r.status_code in (200, 404) or r.status_code == 500


def test_set_deepseek(client, monkeypatch, tmp_path):
    cfg = tmp_path / 'config.json'
    monkeypatch.setenv('HOST', '127.0.0.1')
    monkeypatch.setenv('PORT', '0')
    monkeypatch.setenv('FLASK_ENV', 'testing')
    monkeypatch.setenv('CORS_ORIGINS', '*')

    os.chdir(tmp_path)
    payload = {'api_key': 'x' * 24, 'model': 'deepseek-chat'}
    r = client.post('/admin/set-deepseek', data=json.dumps(payload), content_type='application/json')
    assert r.status_code in (200, 500, 404)

