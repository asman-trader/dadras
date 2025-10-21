import os
from flask import Blueprint, jsonify, make_response, request

admin_logs_bp = Blueprint('admin_logs', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)


def _require_admin_if_configured():
    from app import ADMIN_TOKEN
    if not ADMIN_TOKEN:
        return None
    provided = (
        request.headers.get('X-Admin-Token')
        or request.headers.get('X-Token')
    )
    if not provided or provided.strip() != ADMIN_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    return None


def _tail_file(path: str, max_lines: int = 200) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            if not lines:
                return ''
            return ''.join(lines[-max(1, int(max_lines)):])
    except Exception:
        return ''


@admin_logs_bp.get('/admin/logs')
def admin_logs_json():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    from app import CURRENT_LOG_FILE, DATA_DIR
    try:
        lines = int(request.args.get('lines', '200'))
    except Exception:
        lines = 200
    log_path = os.getenv('LOG_FILE', CURRENT_LOG_FILE or os.path.join(DATA_DIR, 'logs', 'app.log')).strip()
    try:
        size = os.path.getsize(log_path) if os.path.isfile(log_path) else 0
        mtime = os.path.getmtime(log_path) if os.path.isfile(log_path) else 0
    except Exception:
        size = 0
        mtime = 0
    content = _tail_file(log_path, max_lines=lines)
    return jsonify({'path': log_path, 'size': size, 'mtime': mtime, 'lines': lines, 'content': content})


@admin_logs_bp.get('/admin/logs/text')
def admin_logs_text():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    from app import CURRENT_LOG_FILE, DATA_DIR
    try:
        lines = int(request.args.get('lines', '200'))
    except Exception:
        lines = 200
    log_path = os.getenv('LOG_FILE', CURRENT_LOG_FILE or os.path.join(DATA_DIR, 'logs', 'app.log')).strip()
    content = _tail_file(log_path, max_lines=lines)
    resp = make_response(content or '')
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return resp

