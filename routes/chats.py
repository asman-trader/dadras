import os
import re
import uuid
import json as _json
from flask import Blueprint, request, jsonify

chats_bp = Blueprint('chats', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, 'data')


def _ensure_chat_dirs() -> None:
    os.makedirs(os.path.join(DATA_DIR, 'chats'), exist_ok=True)


def _get_client_id() -> str:
    cid = request.cookies.get('client_id')
    if cid and isinstance(cid, str) and len(cid) >= 8:
        return cid
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
                items.append({'id': chat_id, 'title': title, 'mtime': mtime})
            except Exception:
                continue
        items.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'list_failed', 'detail': str(exc)}), 500
    return jsonify({'ok': True, 'items': items})


@chats_bp.post('/chats')
def chats_create():
    _ensure_chat_dirs()
    cid = _get_client_id()
    data = request.get_json(silent=True) or {}
    title = str(data.get('title') or '').strip() or 'گفت‌وگو'
    chat_id = uuid.uuid4().hex[:12]
    path = os.path.join(_chat_dir_for(cid), chat_id + '.json')
    meta = {'id': chat_id, 'title': title, 'created_at': int(uuid.uuid1().time)}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, ensure_ascii=False)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'create_failed', 'detail': str(exc)}), 500
    return jsonify({'ok': True, 'id': chat_id, 'title': title})


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
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, ensure_ascii=False)
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'rename_failed', 'detail': str(exc)}), 500
    return jsonify({'ok': True})


