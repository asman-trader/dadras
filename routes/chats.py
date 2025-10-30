import os
import re
import uuid
import hashlib
import json as _json
from flask import Blueprint, request, jsonify

chats_bp = Blueprint('chats', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, 'data')


def _ensure_chat_dirs() -> None:
    os.makedirs(os.path.join(DATA_DIR, 'chats'), exist_ok=True)


def _get_client_id() -> str:
    """Deterministic client id based on IP + User-Agent; fall back to cookie."""
    try:
        cid = request.cookies.get('client_id')
        if cid and isinstance(cid, str) and len(cid) >= 8:
            return cid
    except Exception:
        pass
    try:
        ip_hdr = (request.headers.get('X-Forwarded-For') or '').strip()
        ip = (ip_hdr.split(',')[0].strip() if ip_hdr else (request.remote_addr or '0.0.0.0'))
        ua = (request.headers.get('User-Agent') or '').strip()
        h = hashlib.sha256(f"{ip}|{ua}".encode('utf-8', 'ignore')).hexdigest()[:24]
        return f"ipua_{h}"
    except Exception:
        return uuid.uuid4().hex


def _chat_dir_for(cid: str) -> str:
    d = os.path.join(DATA_DIR, 'chats', cid)
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_chat_id(s: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF\-]", "_", s or '')
    s = s.strip('_-') or uuid.uuid4().hex[:12]
    return s


@chats_bp.get('/chats')
def chats_list():
    _ensure_chat_dirs()
    cid = _get_client_id()
    base = _chat_dir_for(cid)
    items = []
    try:
        for name in os.listdir(base):
            if not name.lower().endswith('.json'):
                continue
            chat_id = os.path.splitext(name)[0]
            path = os.path.join(base, name)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    meta = _json.load(f) or {}
                title = (meta.get('title') or chat_id)[:80]
                mtime = int(os.stat(path).st_mtime)
                items.append({'id': chat_id, 'title': title, 'mtime': mtime, 'url': f"/c/{chat_id}"})
            except Exception:
                continue
        items.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'list_failed', 'detail': str(exc)}), 500
    r = jsonify({'ok': True, 'items': items})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@chats_bp.post('/chats')
def chats_create():
    _ensure_chat_dirs()
    cid = _get_client_id()
    data = request.get_json(silent=True) or {}
    title = str(data.get('title') or '').strip() or 'گفت‌وگو'
    chat_id = uuid.uuid4().hex[:12]
    path = os.path.join(_chat_dir_for(cid), chat_id + '.json')
    meta = {'id': chat_id, 'title': title, 'created_at': int(uuid.uuid1().time), 'url': f"/c/{chat_id}"}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, ensure_ascii=False)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'create_failed', 'detail': str(exc)}), 500
    r = jsonify({'ok': True, 'id': chat_id, 'title': title, 'url': f"/c/{chat_id}"})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@chats_bp.post('/chats/rename')
def chats_rename():
    _ensure_chat_dirs()
    cid = _get_client_id()
    data = request.get_json(silent=True) or {}
    chat_id = _sanitize_chat_id(data.get('id') or '')
    new_title = str(data.get('title') or '').strip()
    if not chat_id or not new_title:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400
    path = os.path.join(_chat_dir_for(cid), chat_id + '.json')
    if not os.path.isfile(path):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            meta = _json.load(f) or {}
        meta['title'] = new_title
        meta['url'] = f"/c/{chat_id}"
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, ensure_ascii=False)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'rename_failed', 'detail': str(exc)}), 500
    r = jsonify({'ok': True, 'url': f"/c/{chat_id}"})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@chats_bp.delete('/chats')
def chats_delete():
    _ensure_chat_dirs()
    cid = _get_client_id()
    data = request.get_json(silent=True) or {}
    chat_id = _sanitize_chat_id(data.get('id') or '')
    if not chat_id:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400
    path = os.path.join(_chat_dir_for(cid), chat_id + '.json')
    if not os.path.isfile(path):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    try:
        os.remove(path)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'delete_failed', 'detail': str(exc)}), 500
    r = jsonify({'ok': True})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


def _plan_quota_bytes() -> int:
    try:
        # reuse app helper if available
        from app import _plan_storage_quota_bytes
        return int(_plan_storage_quota_bytes())
    except Exception:
        return 10 * 1024 * 1024


def _append_chat_item(cid: str, chat_id: str, item: dict) -> tuple[bool, str]:
    base = _chat_dir_for(cid)
    # enforce per-user quota across all chats
    used = 0
    try:
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                used += os.stat(path).st_size
    except Exception:
        used = 0
    quota = _plan_quota_bytes()
    # rough size of new content
    try:
        import json as _json
        incoming = len((_json.dumps(item, ensure_ascii=False) or '').encode('utf-8'))
    except Exception:
        incoming = len(str(item).encode('utf-8'))
    if (used + incoming) > quota:
        return False, 'quota_exceeded'

    # append to chat file
    import json as _json
    path = os.path.join(base, f'{chat_id}.json')
    data = {}
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    items = data.get('items')
    if not isinstance(items, list):
        items = []
    items.append(item)
    data['id'] = chat_id
    data['items'] = items
    try:
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(data, f, ensure_ascii=False)
    except Exception:
        return False, 'write_failed'
    return True, ''


@chats_bp.post('/chats/append')
def chats_append():
    _ensure_chat_dirs()
    cid = _get_client_id()
    data = request.get_json(silent=True) or {}
    chat_id = _sanitize_chat_id(data.get('id') or '')
    role = str(data.get('role') or '').strip().lower()
    text = str(data.get('text') or '')
    citations = data.get('citations') if isinstance(data.get('citations'), list) else []
    if not chat_id or not role or not text:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400
    ok, err = _append_chat_item(cid, chat_id, {
        'ts': int(__import__('time').time()),
        'role': role,
        'text': text,
        'citations': citations[:6],
    })
    if not ok:
        if err == 'quota_exceeded':
            return jsonify({'ok': False, 'error': 'quota_exceeded'}), 400
        return jsonify({'ok': False, 'error': err}), 500
    r = jsonify({'ok': True})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@chats_bp.get('/chats/get')
def chats_get():
    _ensure_chat_dirs()
    cid = _get_client_id()
    chat_id = _sanitize_chat_id(request.args.get('id') or '')
    if not chat_id:
        return jsonify({'ok': False, 'error': 'bad_request'}), 400
    base = _chat_dir_for(cid)
    path = os.path.join(base, f'{chat_id}.json')
    data = {}
    try:
        if os.path.isfile(path):
            import json as _json
            with open(path, 'r', encoding='utf-8') as f:
                data = _json.load(f) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {'id': chat_id, 'items': []}
    r = jsonify({'ok': True, 'id': chat_id, 'data': data})
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


