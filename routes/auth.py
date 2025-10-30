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
OTP_RATE_PATH = os.path.join(USERS_DIR, 'otp_rate.json')
PAY_SETTINGS_PATH = os.path.join(USERS_DIR, 'payments_settings.json')

# OTP send policy (defaults; can be overridden by env at runtime)
OTP_COOLDOWN_SEC = 60           # min seconds between sends per phone
OTP_WINDOW_SEC = 3600           # rate window (e.g., 1h)
OTP_MAX_PER_WINDOW = 6          # max sends per phone per window
# Fixed Zarinpal merchant ID (user-provided)
ZARINPAL_MERCHANT_ID_FIXED = 'd38153db-0752-4a5b-9723-ad4e10c830a9'
# Fixed payment mode/endpoints (True = sandbox, False = production)
PAYMENT_SANDBOX_FIXED = False
# Plan prices (Toman)
PLAN_PRICE_TOMAN = {
    'plus': 99000,
    'pro': 199000,
    'team': 1990000,
}

def _read_pay_settings() -> Dict[str, Any]:
    d = _read_json(PAY_SETTINGS_PATH)
    return d if isinstance(d, dict) else {}

def _get_subscription_days() -> int:
    d = _read_pay_settings()
    try:
        days = int(d.get('subscription_days', 30))
    except Exception:
        days = 30
    return max(1, min(3650, days))

def _get_price_toman(plan: str) -> int:
    d = _read_pay_settings()
    prices = d.get('prices') if isinstance(d.get('prices'), dict) else {}
    try:
        v = int(prices.get(plan, PLAN_PRICE_TOMAN.get(plan, 0)))
    except Exception:
        v = int(PLAN_PRICE_TOMAN.get(plan, 0))
    return max(0, v)

def _is_mock_mode() -> bool:
    d = _read_pay_settings()
    v = d.get('mock')
    if isinstance(v, bool):
        return v
    return (os.getenv('PAYMENT_MOCK', '0').strip() in ('1', 'true', 'TRUE'))

def _is_sandbox() -> bool:
    d = _read_pay_settings()
    v = d.get('sandbox')
    if isinstance(v, bool):
        return v
    return PAYMENT_SANDBOX_FIXED



def _get_otp_policy() -> Dict[str, int]:
    try:
        cd = int(os.getenv('OTP_COOLDOWN_SEC', str(OTP_COOLDOWN_SEC)))
    except Exception:
        cd = OTP_COOLDOWN_SEC
    try:
        win = int(os.getenv('OTP_WINDOW_SEC', str(OTP_WINDOW_SEC)))
    except Exception:
        win = OTP_WINDOW_SEC
    try:
        mx = int(os.getenv('OTP_MAX_PER_WINDOW', str(OTP_MAX_PER_WINDOW)))
    except Exception:
        mx = OTP_MAX_PER_WINDOW
    return { 'cooldown': max(0, cd), 'window': max(60, win), 'max': max(1, mx) }

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


def _read_rate() -> Dict[str, Any]:
    return _read_json(OTP_RATE_PATH)


def _write_rate(data: Dict[str, Any]) -> None:
    _write_json(OTP_RATE_PATH, data)


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
    # Iran mobile numbers start with 989 followed by 9 digits (total 12)
    return bool(re.fullmatch(r"98(9\d{9})", norm))


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
        # Not configured -> do NOT claim success
        return False
    try:
        import requests
        payload = {
            'to': f'+{phone_norm_98}',
            'from': sender,
            'text': text,
        }
        headers = { 'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'Accept': 'application/json' }
        r = requests.post(api_url, json=payload, headers=headers, timeout=10)
        return r.ok
    except Exception:
        return False


def _send_otp_via_sms_ir(phone_norm_98: str, code: str) -> tuple[bool, str]:
    """Send OTP via SMS.ir Verify API if configured.
    Requires env: SMS_IR_API_KEY, SMS_IR_TEMPLATE_ID. Optional: SMS_IR_VERIFY_URL, SMS_IR_PARAM_NAME
    """
    # Prefer fixed credentials; fallback to envs if absent
    api_key = (SMS_IR_FIXED_API_KEY or os.getenv('SMS_IR_API_KEY', '').strip())
    template_id = (SMS_IR_FIXED_TEMPLATE_ID or os.getenv('SMS_IR_TEMPLATE_ID', '').strip())
    if not api_key or not template_id:
        return False, 'missing_api_key_or_template'
    param_name = (SMS_IR_FIXED_PARAM_NAME or os.getenv('SMS_IR_PARAM_NAME', 'code').strip() or 'code')
    url = os.getenv('SMS_IR_VERIFY_URL', 'https://api.sms.ir/v1/send/verify').strip()
    # Convert 98XXXXXXXXXX to local 09XXXXXXXXX as SMS.ir expects
    mobile_local = ('0' + phone_norm_98[2:]) if phone_norm_98.startswith('98') else phone_norm_98
    try:
        import requests, time as _t
        # Try multiple common parameter names to reduce template mismatch issues
        names = [param_name, 'Code', 'code', 'verificationCode', 'VerificationCode']
        seen = set(); names = [n for n in names if not (n in seen or seen.add(n))]
        body_base = {
            'mobile': mobile_local,
            'templateId': int(template_id) if template_id.isdigit() else template_id,
            'parameters': [ { 'name': n, 'value': code } for n in names ]
        }
        headers = { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-API-KEY': api_key }
        last_detail = ''
        for attempt in range(2):
            try:
                r = requests.post(url, json=body_base, headers=headers, timeout=12)
            except Exception as exc:
                last_detail = f'exception:{exc}'
                if attempt == 0:
                    try: _t.sleep(0.6) 
                    except Exception: pass
                continue
            ok = False
            try:
                j = r.json(); ok = bool(j.get('status') in (1, True) or j.get('success') in (1, True)); last_detail = str(j)[:300]
            except Exception:
                ok = r.ok; 
                try: last_detail = (r.text or '')[:300]
                except Exception: last_detail = ''
            if ok:
                try:
                    from logging import getLogger
                    masked = code[:2] + ('*' * max(0, len(code)-4)) + code[-2:]
                    getLogger().info(f"sms_ir_ok http={r.status_code} mobile={mobile_local} template={template_id} code={masked}")
                except Exception:
                    pass
                return True, last_detail
            if r.status_code in (401,403):
                try:
                    from logging import getLogger
                    getLogger().warning(f"sms_ir_failed http={r.status_code} body={(r.text or '')[:200]} mobile={mobile_local}")
                except Exception:
                    pass
                return False, last_detail or 'auth_failed'
            try:
                from logging import getLogger
                getLogger().warning(f"sms_ir_failed http={r.status_code} body={(r.text or '')[:200]} mobile={mobile_local} attempt={attempt+1}")
            except Exception:
                pass
            if attempt == 0:
                try: _t.sleep(0.8)
                except Exception: pass
        return False, last_detail
    except Exception as exc:
        return False, f'exception:{exc}'


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
        'plan': 'free',
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
    plan = _normalize_plan(fields.get('plan') or '')
    if first_name:
        u['first_name'] = first_name
    if last_name:
        u['last_name'] = last_name
    if role:
        u['role'] = role
    if plan:
        now = int(time.time())
        # Extend or set expiry for paid plans (plus/pro/team). Free clears expiry
        if plan in ('plus','pro','team'):
            duration = _get_subscription_days() * 24 * 3600
            cur_exp = int(u.get('plan_expires_at') or 0)
            base = cur_exp if cur_exp > now else now
            u['plan_expires_at'] = base + duration
        else:
            u.pop('plan_expires_at', None)
        u['plan'] = plan
    u['updated_at'] = int(time.time())
    users[uid] = u
    _write_json(USERS_PATH, users)


def _append_payment_history(uid: str, rec: Dict[str, Any]) -> None:
    """Append a payment record for a user into data/users/payments_history.json.
    Structure: { uid: [ {ts, plan, amount_toman, authority, api, ref_id}, ... ] }
    """
    hist_path = os.path.join(USERS_DIR, 'payments_history.json')
    data = _read_json(hist_path)
    if not isinstance(data, dict):
        data = {}
    arr = data.get(uid)
    if not isinstance(arr, list):
        arr = []
    try:
        # keep latest first, limit length
        rec = {
            'ts': int(time.time()),
            **{k: v for k, v in rec.items() if k in ('plan','amount_toman','authority','api','ref_id')}
        }
        arr.insert(0, rec)
        if len(arr) > 50:
            arr = arr[:50]
    except Exception:
        pass
    data[uid] = arr
    _write_json(hist_path, data)


def _normalize_plan(plan: str) -> str:
    p = (plan or '').strip().lower()
    mapping = {
        'free': 'free', 'رایگان': 'free',
        'plus': 'plus', 'پلاس': 'plus',
        'pro': 'pro', 'حرفه ای': 'pro', 'حرفه‌ای': 'pro',
        'team': 'team', 'سازمانی': 'team'
    }
    return mapping.get(p, '')


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
    # Login/signup views are handled in chat; redirect to home
    return redirect('/')


@auth_bp.get('/auth/signup')
def signup_page():
    # Login/signup views are handled in chat; redirect to home
    return redirect('/')


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
    # Simple per-phone cooldown and hourly rate limit (admin token bypass allowed)
    now = int(time.time())
    # admin bypass
    admin_token = os.getenv('ADMIN_TOKEN', '').strip()
    provided = request.headers.get('X-Admin-Token') or request.headers.get('X-Token')
    bypass = bool(admin_token and provided and provided.strip() == admin_token)

    policy = _get_otp_policy()
    cooldown = int(policy['cooldown'])
    window = int(policy['window'])
    max_per = int(policy['max'])

    rate = _read_rate()
    r = rate.get(norm) or {}
    last = int(r.get('last', 0))
    win_start = int(r.get('win_start', now))
    sent = int(r.get('sent', 0))
    if not bypass and cooldown and (now - last) < cooldown:
        return jsonify({'ok': False, 'error': 'cooldown', 'retry_in_sec': max(1, cooldown - (now - last))}), 429
    if (now - win_start) > window:
        win_start, sent = now, 0
    if not bypass and sent >= max_per:
        return jsonify({'ok': False, 'error': 'rate_limited', 'retry_in_sec': max(1, window - (now - win_start))}), 429

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
    provider_detail = ''
    try:
        sent, provider_detail = _send_otp_via_sms_ir(norm, code)
    except Exception as exc:
        sent = False
        provider_detail = f'exception:{exc}'
    if not sent:
        sent = _send_sms(norm, f"کد ورود شما: {code}")
    if not sent:
        try:
            from logging import getLogger
            masked = code[:2] + ('*' * max(0, len(code)-4)) + code[-2:]
            getLogger().warning(f"otp_send_failed phone=+{norm} code={masked}")
        except Exception:
            pass
        # expose provider hint only to admin requests
        if bypass:
            return jsonify({'ok': False, 'error': 'sms_failed', 'provider': 'sms_ir', 'detail': provider_detail}), 502
        return jsonify({'ok': False, 'error': 'sms_failed'}), 502
    # Update rate counters on success
    try:
        rate[norm] = { 'last': now, 'win_start': win_start, 'sent': sent + 1 }
        _write_rate(rate)
    except Exception:
        pass
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
    # remaining days
    rem_days = 0
    try:
        exp = int((u or {}).get('plan_expires_at') or 0)
        if exp > int(time.time()):
            rem_days = max(0, (exp - int(time.time())) // 86400)
    except Exception:
        rem_days = 0
    return jsonify({'ok': True, 'authenticated': True, 'user': {
        'id': u.get('id'),
        'phone': u.get('phone_norm'),
        'first_name': u.get('first_name', ''),
        'last_name': u.get('last_name', ''),
        'role': u.get('role', ''),
        'plan': u.get('plan', 'free'),
        'plan_expires_at': int(u.get('plan_expires_at') or 0),
        'plan_remaining_days': int(rem_days),
    }})


@auth_bp.get('/pricing')
def pricing_page():
    # Pricing page removed -> redirect to home
    return redirect('/')



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


@auth_bp.get('/auth/plan')
def get_plan():
    u = g.get('current_user') or {}
    rem_days = 0
    try:
        exp = int((u or {}).get('plan_expires_at') or 0)
        if exp > int(time.time()):
            rem_days = max(0, (exp - int(time.time())) // 86400)
    except Exception:
        rem_days = 0
    return jsonify({'ok': True, 'plan': (u.get('plan') or 'free'), 'remaining_days': int(rem_days), 'expires_at': int(u.get('plan_expires_at') or 0)})


@auth_bp.get('/auth/pay/history')
def pay_history():
    u = g.get('current_user') or {}
    if not u:
        return jsonify({'ok': False, 'error': 'auth_required'}), 401
    hist_path = os.path.join(USERS_DIR, 'payments_history.json')
    data = _read_json(hist_path)
    arr = data.get(str(u.get('id'))) if isinstance(data, dict) else []
    if not isinstance(arr, list):
        arr = []
    rem_days = 0
    try:
        exp = int((u or {}).get('plan_expires_at') or 0)
        if exp > int(time.time()):
            rem_days = max(0, (exp - int(time.time())) // 86400)
    except Exception:
        rem_days = 0
    return jsonify({'ok': True, 'plan': (u.get('plan') or 'free'), 'remaining_days': int(rem_days), 'expires_at': int(u.get('plan_expires_at') or 0), 'history': arr})


@auth_bp.post('/auth/plan')
def set_plan():
    u = g.get('current_user') or {}
    if not u:
        return jsonify({'ok': False, 'error': 'auth_required'}), 401
    data = request.get_json(silent=True) or {}
    plan = _normalize_plan(data.get('plan') or '')
    if not plan:
        return jsonify({'ok': False, 'error': 'invalid_plan'}), 400
    try:
        _update_user(str(u.get('id') or ''), {'plan': plan})
        return jsonify({'ok': True, 'plan': plan})
    except Exception:
        return jsonify({'ok': False}), 500


# -------------------- Zarinpal Sandbox Integration --------------------
@auth_bp.post('/auth/pay/start')
def pay_start():
    """Start a Zarinpal sandbox payment and return redirect URL.
    Plans: plus -> 99000, pro -> 199000 (IRR)
    """
    u = g.get('current_user') or {}
    if not u:
        return jsonify({'ok': False, 'error': 'auth_required'}), 401
    plan = _normalize_plan((request.args.get('plan') or request.form.get('plan') or '').strip())
    if plan not in ('plus', 'pro', 'team'):
        return jsonify({'ok': False, 'error': 'invalid_plan'}), 400
    amount_toman = int(PLAN_PRICE_TOMAN.get(plan) or 0)
    amount_rial = amount_toman * 10

    # Zarinpal sandbox endpoints (v4 with v1 fallback)
    merchant_id = ZARINPAL_MERCHANT_ID_FIXED
    # Allow mock mode without merchant id
    mock_mode = (os.getenv('PAYMENT_MOCK', '0').strip() in ('1', 'true', 'TRUE'))
    if (not merchant_id or merchant_id.startswith('XXXX')) and not mock_mode:
        return jsonify({'ok': False, 'error': 'merchant_missing', 'hint': 'Set ZARINPAL_MERCHANT_ID or enable mock via PAYMENT_MOCK=1'}), 400

    sandbox = PAYMENT_SANDBOX_FIXED
    v4_req_url = os.getenv('ZARINPAL_V4_REQUEST_URL', 'https://sandbox.zarinpal.com/pg/v4/payment/request.json' if sandbox else 'https://api.zarinpal.com/pg/v4/payment/request.json')
    v4_verify_url = os.getenv('ZARINPAL_V4_VERIFY_URL', 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json' if sandbox else 'https://api.zarinpal.com/pg/v4/payment/verify.json')
    v1_req_url = os.getenv('ZARINPAL_REQUEST_URL', 'https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentRequest.json' if sandbox else 'https://api.zarinpal.com/pg/rest/WebGate/PaymentRequest.json')
    start_url = os.getenv('ZARINPAL_START_URL', 'https://sandbox.zarinpal.com/pg/StartPay/' if sandbox else 'https://www.zarinpal.com/pg/StartPay/')
    callback_url = os.getenv('ZARINPAL_CALLBACK_URL', '').strip() or (request.url_root.rstrip('/') + '/auth/pay/callback')

    try:
        import requests
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if mock_mode:
            # Simulate authority and redirect immediately to callback as success
            authority = 'MOCK-' + uuid.uuid4().hex[:12]
            pend_path = os.path.join(USERS_DIR, 'payments.json')
            pend = _read_json(pend_path)
            pend[authority] = {'uid': u.get('id'), 'plan': plan, 'amount_toman': amount_toman, 'amount_rial': amount_rial, 'created_at': int(time.time()), 'api': 'mock'}
            _write_json(pend_path, pend)
            cb = (request.url_root.rstrip('/') + f"/auth/pay/callback?Status=OK&Authority={authority}")
            return jsonify({'ok': True, 'url': cb})
        # Try v4 first
        v4_payload = {
            'merchant_id': merchant_id,
            'amount': int(amount_toman),
            'description': f'Dadras subscription upgrade: {plan}',
            'callback_url': callback_url,
            'currency': 'IRT'
        }
        r4 = requests.post(v4_req_url, json=v4_payload, headers=headers, timeout=15)
        j4 = {}
        try:
            j4 = r4.json() or {}
        except Exception:
            j4 = {}
        data4 = j4.get('data') or {}
        if r4.ok and int(data4.get('code') or 0) in (100, 101) and (data4.get('authority')):
            authority = data4['authority']
            # Some integrations require zpl mode, append if configured
            zpl = os.getenv('ZARINPAL_START_QUERY', '')
            url = f"{start_url}{authority}{('?' + zpl) if zpl else ''}"
            pend_path = os.path.join(USERS_DIR, 'payments.json')
            pend = _read_json(pend_path)
            pend[authority] = {'uid': u.get('id'), 'plan': plan, 'amount_toman': amount_toman, 'amount_rial': amount_rial, 'created_at': int(time.time()), 'api': 'v4'}
            _write_json(pend_path, pend)
            return jsonify({'ok': True, 'url': url})

        # Fallback to v1
        v1_payload = {
            'MerchantID': merchant_id,
            'Amount': int(amount_rial),
            'Description': f'Dadras subscription upgrade: {plan}',
            'CallbackURL': callback_url,
        }
        r1 = requests.post(v1_req_url, json=v1_payload, headers=headers, timeout=15)
        j1 = {}
        try:
            j1 = r1.json() or {}
        except Exception:
            j1 = {}
        if r1.ok and (j1.get('Status') in (100, '100')) and j1.get('Authority'):
            authority = j1['Authority']
            zpl = os.getenv('ZARINPAL_START_QUERY', '')
            url = f"{start_url}{authority}{('?' + zpl) if zpl else ''}"
            pend_path = os.path.join(USERS_DIR, 'payments.json')
            pend = _read_json(pend_path)
            pend[authority] = {'uid': u.get('id'), 'plan': plan, 'amount_toman': amount_toman, 'amount_rial': amount_rial, 'created_at': int(time.time()), 'api': 'v1'}
            _write_json(pend_path, pend)
            return jsonify({'ok': True, 'url': url})

        return jsonify({'ok': False, 'error': 'request_failed', 'detail': (j4 or j1 or {})}), 502
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'exception', 'detail': str(exc)}), 500


@auth_bp.get('/auth/pay/callback')
def pay_callback():
    """Zarinpal callback verification (sandbox)."""
    try:
        authority = (request.args.get('Authority') or '').strip()
        status = (request.args.get('Status') or '').strip()
        if not authority:
            return redirect('/auth/profile')
        pend_path = os.path.join(USERS_DIR, 'payments.json')
        pend = _read_json(pend_path)
        intent = pend.get(authority) or {}
        if status.lower() != 'ok' or not intent:
            # cleanup and redirect
            try:
                pend.pop(authority, None); _write_json(pend_path, pend)
            except Exception:
                pass
            return redirect('/auth/profile')

        # Verify payment (try v4 then v1)
        merchant_id = ZARINPAL_MERCHANT_ID_FIXED
        sandbox = PAYMENT_SANDBOX_FIXED
        v4_verify_url = os.getenv('ZARINPAL_V4_VERIFY_URL', 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json' if sandbox else 'https://api.zarinpal.com/pg/v4/payment/verify.json')
        v1_verify_url = os.getenv('ZARINPAL_VERIFY_URL', 'https://sandbox.zarinpal.com/pg/rest/WebGate/PaymentVerification.json' if sandbox else 'https://api.zarinpal.com/pg/rest/WebGate/PaymentVerification.json')
        try:
            import requests
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            # For v4 (IRT), for v1 (IRR)
            amount_toman = int(intent.get('amount_toman') or 0)
            amount_rial = int(intent.get('amount_rial') or (amount_toman * 10))
            amount = amount_toman
            # v4
            v4_payload = { 'merchant_id': merchant_id, 'authority': authority, 'amount': amount }
            rv4 = requests.post(v4_verify_url, json=v4_payload, headers=headers, timeout=15)
            jv4 = {}
            try:
                jv4 = rv4.json() or {}
            except Exception:
                jv4 = {}
            data4 = jv4.get('data') or {}
            if rv4.ok and int(data4.get('code') or 0) in (100, 101):
                uid = str(intent.get('uid') or '')
                plan = str(intent.get('plan') or '')
                if uid and plan:
                    try:
                        _update_user(uid, {'plan': plan})
                        _append_payment_history(uid, {
                            'plan': plan,
                            'amount_toman': int(intent.get('amount_toman') or 0),
                            'authority': authority,
                            'api': 'v4',
                            'ref_id': str((data4.get('ref_id') or ''))
                        })
                    except Exception:
                        pass
                try:
                    pend.pop(authority, None); _write_json(pend_path, pend)
                except Exception:
                    pass
                return redirect('/auth/profile')

            # v1 fallback
            v1_payload = { 'MerchantID': merchant_id, 'Authority': authority, 'Amount': amount_rial }
            rv1 = requests.post(v1_verify_url, json=v1_payload, headers=headers, timeout=15)
            jv1 = {}
            try:
                jv1 = rv1.json() or {}
            except Exception:
                jv1 = {}
            if rv1.ok and (jv1.get('Status') in (100, '100')):
                uid = str(intent.get('uid') or '')
                plan = str(intent.get('plan') or '')
                if uid and plan:
                    try:
                        _update_user(uid, {'plan': plan})
                        _append_payment_history(uid, {
                            'plan': plan,
                            'amount_toman': int(intent.get('amount_toman') or 0),
                            'authority': authority,
                            'api': 'v1',
                            'ref_id': str((jv1.get('RefID') or jv1.get('ref_id') or ''))
                        })
                    except Exception:
                        pass
                try:
                    pend.pop(authority, None); _write_json(pend_path, pend)
                except Exception:
                    pass
                return redirect('/auth/profile')
        except Exception:
            pass
        # failed or not verified
        try:
            pend.pop(authority, None); _write_json(pend_path, pend)
        except Exception:
            pass
        return redirect('/auth/profile')
    except Exception:
        return redirect('/auth/profile')