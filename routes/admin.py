import os
from flask import Blueprint, jsonify, render_template, make_response, request

admin_bp = Blueprint('admin', __name__)

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


@admin_bp.get('/admin')
def admin_page():
    home_path = os.path.join(APP_DIR, 'templates', 'admin', 'home.html')
    if os.path.exists(home_path):
        return render_template('admin/home.html')
    legacy = os.path.join(APP_DIR, 'templates', 'admin', 'legacy.html')
    if os.path.exists(legacy):
        return render_template('admin/legacy.html')
    return make_response('<p>admin page not found</p>', 404)


@admin_bp.get('/admin/llm')
def admin_llm_page():
    llm_path = os.path.join(APP_DIR, 'templates', 'admin', 'llm.html')
    if os.path.exists(llm_path):
        return render_template('admin/llm.html')
    return make_response('<p>admin llm page not found</p>', 404)


@admin_bp.get('/admin/data')
def admin_data_page():
    data_path = os.path.join(APP_DIR, 'templates', 'admin', 'data.html')
    if os.path.exists(data_path):
        return render_template('admin/data.html')
    return make_response('<p>admin data page not found</p>', 404)


@admin_bp.get('/admin/logs/view')
def admin_logs_page():
    log_tpl = os.path.join(APP_DIR, 'templates', 'admin', 'log.html')
    if os.path.exists(log_tpl):
        return render_template('admin/log.html')
    return make_response('<p>admin log page not found</p>', 404)

