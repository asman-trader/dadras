import os
import json as _json
from flask import Blueprint, jsonify, request

admin_api_bp = Blueprint('admin_api', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)


def _require_admin_if_configured():
    from app import ADMIN_TOKEN  # reuse from app
    if not ADMIN_TOKEN:
        return None
    provided = (
        request.headers.get('X-Admin-Token')
        or request.headers.get('X-Token')
    )
    if not provided or provided.strip() != ADMIN_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    return None


@admin_api_bp.get('/admin/stats')
def admin_stats():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    from app import LOADED_FILES, PARAGRAPHS, INVERTED, DATA_DIR, CONFIG_PATH
    from app import DEEPSEEK_TIMEOUT_SEC, DEEPSEEK_MAX_RETRIES, CURRENT_LOG_FILE
    cfg = {}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = _json.load(f) or {}
    except Exception:
        cfg = {}
    return jsonify({
        'files': len(LOADED_FILES),
        'paragraphs': len(PARAGRAPHS),
        'vocab': len(INVERTED),
        'data_dir': DATA_DIR,
        'app_version': os.getenv('APP_VERSION', '1.0.0'),
        'log': {
            'file': CURRENT_LOG_FILE,
            'level': str(os.getenv('LOG_LEVEL', 'INFO')).upper().strip() or 'INFO',
        },
        'llm': {
            'use_deepseek': os.getenv('USE_DEEPSEEK', ''),
            'deepseek_model': os.getenv('DEEPSEEK_MODEL', ''),
            'deepseek_key_set': bool(os.getenv('DEEPSEEK_API_KEY', '').strip()),
            'deepseek_base_url': os.getenv('DEEPSEEK_BASE_URL', ''),
            'deepseek_timeout_sec': DEEPSEEK_TIMEOUT_SEC,
            'deepseek_max_retries': DEEPSEEK_MAX_RETRIES,
            'use_ollama': os.getenv('USE_OLLAMA', ''),
            'ollama_host': os.getenv('OLLAMA_HOST', ''),
            'ollama_model': os.getenv('OLLAMA_MODEL', ''),
        },
        'config_exists': os.path.exists(CONFIG_PATH),
    })


@admin_api_bp.get('/admin/config')
def admin_get_config():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    from app import CONFIG_PATH
    cfg = {}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = _json.load(f) or {}
    except Exception:
        cfg = {}
    masked = {}
    key_set = False
    key_masked = ''
    for k, v in cfg.items():
        if 'KEY' in k:
            s = str(v or '')
            key_set = key_set or bool(s)
            mv = ('***' if len(s) <= 6 else ('*'*(len(s)-4))+s[-4:])
            masked[k] = mv
            if k == 'DEEPSEEK_API_KEY':
                key_masked = mv
        else:
            masked[k] = v
    masked['DEEPSEEK_API_KEY_SET'] = key_set
    if key_masked:
        masked['DEEPSEEK_API_KEY_MASKED'] = key_masked
    return jsonify(masked)


@admin_api_bp.post('/admin/config')
def admin_set_config():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    from app import CONFIG_PATH, _apply_config_to_env, _write_config, _setup_logging
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'invalid_body'}), 400
    cfg = {}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = _json.load(f) or {}
    except Exception:
        cfg = {}
    allow = {
        'USE_DEEPSEEK', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL',
        'DEEPSEEK_TIMEOUT_SEC', 'DEEPSEEK_MAX_RETRIES',
        'USE_OLLAMA', 'OLLAMA_HOST', 'OLLAMA_MODEL',
        'LOG_LEVEL', 'LOG_FILE', 'APP_VERSION'
    }
    for k, v in data.items():
        if k in allow:
            cfg[k] = v
    if not _write_config(cfg):
        return jsonify({'ok': False}), 500
    _apply_config_to_env(cfg)
    try:
        _setup_logging()
    except Exception:
        pass
    return jsonify({'ok': True})

