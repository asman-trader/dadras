import os
import re
import uuid
import time
import json as _json
from typing import Dict, Any
from flask import Blueprint, request, jsonify, make_response, render_template, g, redirect


auth_bp = Blueprint('auth', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, 'data')
USERS_DIR = os.path.join(DATA_DIR, 'users')
USERS_PATH = os.path.join(USERS_DIR, 'users.json')
SESSIONS_PATH = os.path.join(USERS_DIR, 'sessions.json')
OTP_PATH = os.path.join(USERS_DIR, 'otp.json')

# Fixed SMS.ir credentials per user request
SMS_IR_FIXED_API_KEY = 'bzmyaSCXVBV2G8WI8e8bZsPo56yJ7zwymBisAIwdN3WEgdGa'
SMS_IR_FIXED_TEMPLATE_ID = '335146'
SMS_IR_FIXED_PARAM_NAME = 'code'


def _ensure_users_dir() -> None:
    os.makedirs(USERS_DIR, exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return _json.load(f) or {}
    except Exception:
        return {}
    return {}


def _write_json(path: str, data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(data or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _normalize_phone(phone: str) -> str:
    p = (phone or '').strip()
    p = re.sub(r"[^\d+]", "", p)
    # Accept formats: 09XXXXXXXXX, +989XXXXXXXXX, 989XXXXXXXXX
    if p.startswith('+'):
        p = p[1:]
    if p.startswith('0098'):
        p = '98' + p[4:]
    if p.startswith('98'):
        if len(p) == 12 and p[2] == '9':
            return p
    if p.startswith('09') and len(p) == 11:
        return '98' + p[1:]
    return p


def _valid_phone_norm(norm: str) -> bool:
    return bool(re.fullmatch(r"98\d{10}", norm))


def _send_sms(phone_norm_98: str, text: str) -> bool:
    """Pluggable SMS sender. If no provider configured, log-only and return True."""
    api_url = os.getenv('SMS_API_URL', '').strip()
    api_key = os.getenv('SMS_API_KEY', '').strip()
    sender = os.getenv('SMS_SENDER', '').strip()
    if not api_url or not api_key:
        try:
            from logging import getLogger
            getLogger().info(f"[SMS] to=+{phone_norm_98} body={text}")
        except Exception:
            pass
        return True
    try:
        import requests
        payload = {
            'to': f'+{phone_norm_98}',
            'from': sender,
            'text': text,
        }
        headers = { 'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json' }
        r = requests.post(api_url, json=payload, headers=headers, timeout=10)
        return r.ok
    except Exception:
        return False


def _send_otp_via_sms_ir(phone_norm_98: str, code: str) -> bool:
    """Send OTP via SMS.ir Verify API if configured.
    Requires env: SMS_IR_API_KEY, SMS_IR_TEMPLATE_ID. Optional: SMS_IR_VERIFY_URL, SMS_IR_PARAM_NAME
    """
    # Prefer fixed credentials; fallback to envs if absent
    api_key = (SMS_IR_FIXED_API_KEY or os.getenv('SMS_IR_API_KEY', '').strip())
    template_id = (SMS_IR_FIXED_TEMPLATE_ID or os.getenv('SMS_IR_TEMPLATE_ID', '').strip())
    if not api_key or not template_id:
        return False
    param_name = (SMS_IR_FIXED_PARAM_NAME or os.getenv('SMS_IR_PARAM_NAME', 'code').strip() or 'code')
    url = os.getenv('SMS_IR_VERIFY_URL', 'https://api.sms.ir/v1/send/verify').strip()
    # Convert 98XXXXXXXXXX to local 09XXXXXXXXX as SMS.ir expects
    mobile_local = ('0' + phone_norm_98[2:]) if phone_norm_98.startswith('98') else phone_norm_98
    try:
        import requests
        # Try multiple common parameter names to reduce template mismatch issues
        tried_names = []
        names = [param_name, 'Code', 'code', 'verificationCode', 'VerificationCode']
        # de-duplicate while preserving order
        seen = set()
        names = [n for n in names if not (n in seen or seen.add(n))]
        body = {
            'mobile': mobile_local,
            'templateId': int(template_id) if template_id.isdigit() else template_id,
            'parameters': [ { 'name': n, 'value': code } for n in names ]
        }
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }
        r = requests.post(url, json=body, headers=headers, timeout=10)
        if not r.ok:
            try:
                from logging import getLogger
                getLogger().warning(f"sms_ir_failed status={r.status_code} body={(r.text or '')[:200]} mobile={mobile_local}")
            except Exception:
                pass
        return r.ok
    except Exception:
        return False


def _issue_session(user_id: str) -> str:
    _ensure_users_dir()
    sessions = _read_json(SESSIONS_PATH)
    token = uuid.uuid4().hex
    sessions[token] = {
        'user_id': user_id,
        'created_at': int(time.time()),
        'expires_at': int(time.time()) + 30*24*3600,
    }
    _write_json(SESSIONS_PATH, sessions)
    return token


def _find_user_by_phone(phone_norm_98: str) -> str:
    users = _read_json(USERS_PATH)
    for uid, u in users.items():
        if (u.get('phone_norm') or '') == phone_norm_98:
            return uid
    return ''


def _get_user(uid: str) -> Dict[str, Any]:
    users = _read_json(USERS_PATH)
    return users.get(uid) or {}


def _create_user(phone_norm_98: str) -> str:
    _ensure_users_dir()
    users = _read_json(USERS_PATH)
    uid = uuid.uuid4().hex
    users[uid] = {
        'id': uid,
        'phone_norm': phone_norm_98,
        'created_at': int(time.time()),
    }
    _write_json(USERS_PATH, users)
    return uid


def _normalize_role(role: str) -> str:
    r = (role or '').strip().lower()
    # accept Persian labels too
    if r in ('شهروند', 'citizen', 'user'):
        return 'citizen'
    if r in ('وکیل', 'lawyer', 'attorney'):
        return 'lawyer'
    if r in ('قاضی', 'judge'):
        return 'judge'
    return ''


def _update_user(uid: str, fields: Dict[str, Any]) -> None:
    if not uid:
        return
    users = _read_json(USERS_PATH)
    u = users.get(uid)
    if not isinstance(u, dict):
        return
    first_name = (fields.get('first_name') or '').strip()
    last_name = (fields.get('last_name') or '').strip()
    role = _normalize_role(fields.get('role') or '')
    if first_name:
        u['first_name'] = first_name
    if last_name:
        u['last_name'] = last_name
    if role:
        u['role'] = role
    u['updated_at'] = int(time.time())
    users[uid] = u
    _write_json(USERS_PATH, users)


@auth_bp.before_app_request
def _load_current_user():
    try:
        token = request.cookies.get('session_token') or ''
        if not token:
            g.current_user = None
            return
        sessions = _read_json(SESSIONS_PATH)
        sess = sessions.get(token)
        if not sess:
            g.current_user = None
            return
        if int(sess.get('expires_at') or 0) < int(time.time()):
            # expired session -> delete and clear
            try:
                sessions.pop(token, None)
                _write_json(SESSIONS_PATH, sessions)
            except Exception:
                pass
            g.current_user = None
            return
        user = _get_user(str(sess.get('user_id') or ''))
        g.current_user = user if user else None
    except Exception:
        g.current_user = None


@auth_bp.app_context_processor
def _inject_current_user():
    return { 'current_user': g.get('current_user') }


@auth_bp.get('/auth/login')
def login_page():
    return render_template('auth/login.html')


@auth_bp.get('/auth/signup')
def signup_page():
    return render_template('auth/signup.html')


@auth_bp.post('/auth/send-otp')
def send_otp():
    _ensure_users_dir()
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    purpose = (data.get('purpose') or 'login').strip()
    norm = _normalize_phone(phone)
    if not _valid_phone_norm(norm):
        return jsonify({'ok': False, 'error': 'invalid_phone'}), 400
    # For signup, optionally ensure user not exist
    if purpose == 'signup':
        if _find_user_by_phone(norm):
            return jsonify({'ok': False, 'error': 'already_registered'}), 409
    # Generate and store OTP
    otp_store = _read_json(OTP_PATH)
    code = str(uuid.uuid4().int % 1000000).zfill(6)
    otp_store[norm] = {
        'code': code,
        'purpose': purpose,
        'expires_at': int(time.time()) + 2*60,
        'tries_left': 5,
    }
    _write_json(OTP_PATH, otp_store)
    # Prefer SMS.ir if configured; fallback to plain text sender
    sent = False
    try:
        sent = _send_otp_via_sms_ir(norm, code)
    except Exception:
        sent = False
    if not sent:
        sent = _send_sms(norm, f"کد ورود شما: {code}")
    if not sent:
        try:
            from logging import getLogger
            masked = code[:2] + ('*' * max(0, len(code)-4)) + code[-2:]
            getLogger().warning(f"otp_send_failed phone=+{norm} code={masked}")
        except Exception:
            pass
        return jsonify({'ok': False, 'error': 'sms_failed'}), 502
    return jsonify({'ok': True})


@auth_bp.post('/auth/verify-otp')
def verify_otp():
    _ensure_users_dir()
    data = request.get_json(silent=True) or {}
    phone = (data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()
    purpose = (data.get('purpose') or 'login').strip()
    norm = _normalize_phone(phone)
    if not _valid_phone_norm(norm) or not re.fullmatch(r"\d{4,8}", code):
        return jsonify({'ok': False, 'error': 'invalid_input'}), 400
    otp_store = _read_json(OTP_PATH)
    rec = otp_store.get(norm)
    if not rec:
        return jsonify({'ok': False, 'error': 'no_otp'}), 400
    if int(rec.get('expires_at') or 0) < int(time.time()):
        otp_store.pop(norm, None); _write_json(OTP_PATH, otp_store)
        return jsonify({'ok': False, 'error': 'expired'}), 400
    if str(rec.get('code')) != code:
        # decrement tries
        tries = int(rec.get('tries_left') or 0) - 1
        rec['tries_left'] = tries
        otp_store[norm] = rec
        _write_json(OTP_PATH, otp_store)
        return jsonify({'ok': False, 'error': 'wrong_code', 'tries_left': max(0, tries)}), 400
    # success -> consume otp
    otp_store.pop(norm, None)
    _write_json(OTP_PATH, otp_store)
    uid = _find_user_by_phone(norm)
    if purpose == 'signup' and not uid:
        uid = _create_user(norm)
    if not uid:
        # login purpose but user not found -> auto provision
        uid = _create_user(norm)
    # On signup, persist additional profile fields if provided
    if purpose == 'signup':
        extra = {
            'first_name': (data.get('first_name') or '').strip(),
            'last_name': (data.get('last_name') or '').strip(),
            'role': (data.get('role') or '').strip(),
        }
        try:
            _update_user(uid, extra)
        except Exception:
            pass
    token = _issue_session(uid)
    r = make_response(jsonify({'ok': True}))
    r.set_cookie('session_token', token, max_age=30*24*3600, httponly=True, samesite='Lax')
    return r


@auth_bp.get('/auth/logout')
def logout():
    token = request.cookies.get('session_token') or ''
    if token:
        try:
            sessions = _read_json(SESSIONS_PATH)
            sessions.pop(token, None)
            _write_json(SESSIONS_PATH, sessions)
        except Exception:
            pass
    r = redirect('/')
    r.delete_cookie('session_token')
    return r


@auth_bp.get('/auth/me')
def me():
    u = g.get('current_user')
    if not u:
        return jsonify({'ok': False, 'authenticated': False}), 200
    return jsonify({'ok': True, 'authenticated': True, 'user': {
        'id': u.get('id'),
        'phone': u.get('phone_norm'),
        'first_name': u.get('first_name', ''),
        'last_name': u.get('last_name', ''),
        'role': u.get('role', ''),
    }})



@auth_bp.get('/auth/profile')
def profile_page():
    # Redirect guests to login
    if not g.get('current_user'):
        return redirect('/auth/login')
    return render_template('auth/profile.html')


@auth_bp.get('/auth/files')
def profile_files():
    # List downloadable files created by drafts (data/output)
    out_dir = os.path.join(DATA_DIR, 'output')
    items = []
    try:
        if os.path.isdir(out_dir):
            for name in os.listdir(out_dir):
                path = os.path.join(out_dir, name)
                if os.path.isfile(path) and name.lower().endswith('.txt'):
                    st = os.stat(path)
                    items.append({ 'name': name, 'size': int(st.st_size), 'mtime': int(st.st_mtime) })
        items.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception:
        items = []
    return jsonify({'ok': True, 'items': items})

