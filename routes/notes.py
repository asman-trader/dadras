import os
import re
import uuid
from flask import Blueprint, request, jsonify, make_response
from flask import g

notes_bp = Blueprint('notes', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, 'data')


def _ensure_data_dirs_notes() -> None:
    for sub in ('texts',):
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)


def _get_client_id_from_cookie() -> str:
    cid = request.cookies.get('client_id')
    if cid and isinstance(cid, str) and len(cid) >= 8:
        return cid
    return uuid.uuid4().hex


def _notes_dir_for(cid: str) -> str:
    d = os.path.join(DATA_DIR, 'texts', cid)
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_note_id(s: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF\-]", "_", s or '')
    s = s.strip('_-') or uuid.uuid4().hex[:12]
    return s


def _read_note_title_from_content(content: str) -> str:
    if not content:
        return ''
    for line in (content.splitlines() or []):
        t = line.strip()
        if t:
            return t[:80]
    return ''


@notes_bp.get('/notes')
def get_notes():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    qcid = (request.args.get('cid') or '').strip()
    if qcid and len(qcid) >= 8:
        cid = qcid
    path = os.path.join(DATA_DIR, 'texts', f'{cid}.txt')
    txt = ''
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                txt = f.read()
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'read_failed', 'detail': str(exc)}), 500
    r = make_response(jsonify({'ok': True, 'client_id': cid, 'notes': txt}))
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@notes_bp.post('/notes')
def save_notes():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    data = request.get_json(silent=True) or {}
    txt = str(data.get('notes') or '')
    # Enforce per-plan quota using total size of user's notes directory
    try:
        from app import _plan_storage_quota_bytes
        quota = int(_plan_storage_quota_bytes())
    except Exception:
        quota = 10 * 1024 * 1024
    base_dir = _notes_dir_for(cid)
    # compute current usage
    used = 0
    try:
        for name in os.listdir(base_dir):
            path = os.path.join(base_dir, name)
            if os.path.isfile(path):
                used += os.stat(path).st_size
    except Exception:
        used = 0
    incoming = len(txt.encode('utf-8'))
    if (used + incoming) > quota:
        return jsonify({'ok': False, 'error': 'quota_exceeded', 'quota_bytes': int(quota), 'used_bytes': int(used)}), 400
    path = os.path.join(DATA_DIR, 'texts', f'{cid}.txt')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(txt)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'write_failed', 'detail': str(exc)}), 500
    r = make_response(jsonify({'ok': True, 'client_id': cid}))
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@notes_bp.get('/notes/list')
def notes_list():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    base = _notes_dir_for(cid)
    items = []
    try:
        for name in os.listdir(base):
            if not name.lower().endswith('.txt'):
                continue
            nid = os.path.splitext(name)[0]
            path = os.path.join(base, name)
            try:
                st = os.stat(path)
                title = ''
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        title = _read_note_title_from_content(f.read()) or nid
                except Exception:
                    title = nid
                items.append({'id': nid, 'title': title, 'mtime': int(st.st_mtime)})
            except Exception:
                continue
        items.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'list_failed', 'detail': str(exc)}), 500
    r = make_response(jsonify({'ok': True, 'client_id': cid, 'items': items}))
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@notes_bp.get('/notes/get')
def notes_get():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    nid = _sanitize_note_id(request.args.get('id') or '')
    if not nid:
        return jsonify({'ok': False, 'error': 'missing_id'}), 400
    base = _notes_dir_for(cid)
    path = os.path.join(base, nid + '.txt')
    if not os.path.isfile(path):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'read_failed', 'detail': str(exc)}), 500
    title = _read_note_title_from_content(content) or nid
    r = make_response(jsonify({'ok': True, 'client_id': cid, 'id': nid, 'title': title, 'content': content}))
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@notes_bp.post('/notes/save')
def notes_save():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    data = request.get_json(silent=True) or {}
    nid = _sanitize_note_id(data.get('id') or '')
    title = (data.get('title') or '').strip()
    content = str(data.get('content') or '')
    if len(content) > 500_000:
        return jsonify({'ok': False, 'error': 'too_large'}), 400
    base = _notes_dir_for(cid)
    if not nid:
        nid = uuid.uuid4().hex[:12]
    path = os.path.join(base, nid + '.txt')
    if title:
        body = content
        if not body.startswith(title):
            body = title + ('' if content.startswith('\n') else '\n') + content
        content_to_write = body
    else:
        content_to_write = content
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content_to_write)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'write_failed', 'detail': str(exc)}), 500
    r = make_response(jsonify({'ok': True, 'client_id': cid, 'id': nid}))
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@notes_bp.post('/notes/delete')
def notes_delete():
    _ensure_data_dirs_notes()
    cid = _get_client_id_from_cookie()
    data = request.get_json(silent=True) or {}
    nid = _sanitize_note_id(data.get('id') or '')
    if not nid:
        return jsonify({'ok': False, 'error': 'missing_id'}), 400
    base = _notes_dir_for(cid)
    path = os.path.join(base, nid + '.txt')
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'delete_failed', 'detail': str(exc)}), 500
    return jsonify({'ok': True, 'client_id': cid, 'id': nid})


