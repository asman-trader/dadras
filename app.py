from flask import Flask, request, jsonify, render_template, make_response, g
import os
import re
import uuid
import time
from typing import List, Dict, Set, Tuple
import json as _json
import urllib.request as _u
import urllib.error as _ue
import logging
from logging.handlers import TimedRotatingFileHandler
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)
# Register decoupled admin routes
try:
    from routes import all_blueprints
    for bp in all_blueprints:
        app.register_blueprint(bp)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '').strip()
APP_VERSION = os.getenv('APP_VERSION', '1.0.0').strip() or '1.0.0'
try:
    RATE_LIMIT_ASK = int(os.getenv('RATE_LIMIT_ASK', '30'))  # requests
except Exception:
    RATE_LIMIT_ASK = 30
try:
    RATE_WINDOW_SEC = int(os.getenv('RATE_WINDOW_SEC', '60'))
except Exception:
    RATE_WINDOW_SEC = 60

# LLM/HTTP robustness knobs
try:
    DEEPSEEK_TIMEOUT_SEC = float(os.getenv('DEEPSEEK_TIMEOUT_SEC', '15'))
except Exception:
    DEEPSEEK_TIMEOUT_SEC = 15.0
try:
    DEEPSEEK_MAX_RETRIES = int(os.getenv('DEEPSEEK_MAX_RETRIES', '3'))
except Exception:
    DEEPSEEK_MAX_RETRIES = 3

# Default DeepSeek API key (used only if env/config is unset)
DEFAULT_DEEPSEEK_API_KEY = 'sk-de7367663e3a4f43a5c315f63dd516cd'

# In-memory corpus and index
LOADED_FILES: List[str] = []
PARAGRAPHS: List[str] = []
PAR_SOURCE: List[str] = []  # file path per paragraph (txt/pdf)
INVERTED: Dict[str, Set[int]] = {}
SESSION_CTX: Dict[str, List[Dict[str, str]]] = {}
RATE_STATE: Dict[str, List[float]] = {}
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
TEXTS_DIR = os.path.join(DATA_DIR, 'texts')


def _ensure_data_dirs() -> None:
    for sub in ('cases', 'templates', 'output', 'logs', 'texts'):
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
# Logging setup
CURRENT_LOG_FILE = ''


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rid = getattr(g, 'request_id', '-')
        except Exception:
            rid = '-'
        record.request_id = rid
        try:
            record.remote_addr = request.remote_addr or '-'
            record.method = request.method
            record.path = request.path
        except Exception:
            record.remote_addr = '-'
            record.method = '-'
            record.path = '-'
        return True


def _setup_logging() -> None:
    global CURRENT_LOG_FILE
    _ensure_data_dirs()
    level_name = str(os.getenv('LOG_LEVEL', 'INFO')).upper().strip() or 'INFO'
    try:
        level = getattr(logging, level_name, logging.INFO)
    except Exception:
        level = logging.INFO
    log_path = os.getenv('LOG_FILE', os.path.join(DATA_DIR, 'logs', 'app.log')).strip()
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    except Exception:
        pass
    handler = TimedRotatingFileHandler(log_path, when='midnight', backupCount=7, encoding='utf-8')
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(request_id)s %(remote_addr)s %(method)s %(path)s - %(message)s')
    handler.setFormatter(fmt)
    handler.addFilter(RequestContextFilter())
    root = logging.getLogger()
    if not any(isinstance(h, TimedRotatingFileHandler) and getattr(h, 'baseFilename', '') == getattr(handler, 'baseFilename', '') for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(level)
    # also attach to Flask app logger
    if not any(isinstance(h, TimedRotatingFileHandler) and getattr(h, 'baseFilename', '') == getattr(handler, 'baseFilename', '') for h in app.logger.handlers):
        app.logger.addHandler(handler)
    app.logger.setLevel(level)
    CURRENT_LOG_FILE = log_path


# Global HTTP session with retries and pooling
HTTP_SESSION: requests.Session = None  # type: ignore


def _build_retry(total: int = 3, backoff: float = 0.3) -> Retry:
    return Retry(
        total=total,
        connect=total,
        read=total,
        status=total,
        backoff_factor=backoff,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=(
            'HEAD','GET','POST','PUT','DELETE','OPTIONS','TRACE','PATCH'
        ),
        raise_on_status=False,
        respect_retry_after_header=True,
    )


def _get_http_session() -> requests.Session:
    global HTTP_SESSION
    if HTTP_SESSION is not None:
        return HTTP_SESSION
    sess = requests.Session()
    retries = _build_retry(total=max(1, DEEPSEEK_MAX_RETRIES))
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    HTTP_SESSION = sess
    return sess


def _http_request_json(method: str, url: str, headers: Dict[str, str] = None, json_body: object = None, timeout: float = None) -> Tuple[int, Dict[str, object], str]:
    """Perform HTTP request via shared session, return (status, json_or_empty, error_or_empty)."""
    h = dict(headers or {})
    if json_body is not None:
        h.setdefault('Content-Type', 'application/json')
    to = float(timeout if timeout is not None else DEEPSEEK_TIMEOUT_SEC)
    sess = _get_http_session()
    try:
        resp = sess.request(method.upper(), url, headers=h, json=json_body, timeout=to)
        ct = resp.headers.get('content-type', '')
        if 'application/json' in ct.lower():
            try:
                return resp.status_code, (resp.json() or {}), ''
            except Exception as exc:
                app.logger.warning(f"json parse failed url={url} status={resp.status_code} err={exc}")
                return resp.status_code, {}, f'json_parse_error: {exc}'
        return resp.status_code, {}, ''
    except Exception as exc:
        app.logger.warning(f"http error method={method} url={url} err={exc}")
        return 0, {}, str(exc)


# Initialize logging as early as possible
try:
    _setup_logging()
except Exception:
    pass


@app.before_request
def _log_request_start():
    try:
        g.start_ts = time.time()
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        g.request_id = rid
    except Exception:
        g.start_ts = time.time()
        g.request_id = uuid.uuid4().hex


@app.after_request
def _log_request_end(response):
    try:
        dur_ms = int((time.time() - getattr(g, 'start_ts', time.time())) * 1000)
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        app.logger.info(f"request completed status={response.status_code} duration_ms={dur_ms}")
    except Exception:
        pass
    try:
        if not request.cookies.get('client_id'):
            response.set_cookie('client_id', _get_client_id(), max_age=30*24*3600, httponly=False, samesite='Lax')
    except Exception:
        pass
    return response


@app.before_request
def _auto_user_by_ip():
    """Always attach a lightweight user object based on client IP.
    This replaces the login/signup flow and ensures templates and
    rate limiting have a stable identifier.
    """
    try:
        uid = _get_client_id()
        g.current_user = {
            'id': uid,
            'phone_norm': '',
            'plan': 'free',
            'role': 'citizen',
        }
    except Exception:
        try:
            g.current_user = {'id': 'ipua:unknown', 'phone_norm': '', 'plan': 'free', 'role': 'citizen'}
        except Exception:
            pass

def _read_config() -> Dict[str, object]:
    _ensure_data_dirs()
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return _json.load(f) or {}
    except Exception:
        return {}
    return {}


def _write_config(cfg: Dict[str, object]) -> bool:
    _ensure_data_dirs()
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            _json.dump(cfg or {}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _apply_config_to_env(cfg: Dict[str, object]) -> None:
    # DeepSeek
    if 'DEEPSEEK_API_KEY' in cfg:
        os.environ['DEEPSEEK_API_KEY'] = str(cfg.get('DEEPSEEK_API_KEY') or '')
    if 'DEEPSEEK_MODEL' in cfg:
        os.environ['DEEPSEEK_MODEL'] = str(cfg.get('DEEPSEEK_MODEL') or '')
    if 'DEEPSEEK_BASE_URL' in cfg:
        os.environ['DEEPSEEK_BASE_URL'] = str(cfg.get('DEEPSEEK_BASE_URL') or '')
    if 'USE_DEEPSEEK' in cfg:
        os.environ['USE_DEEPSEEK'] = str(cfg.get('USE_DEEPSEEK') or '')
    if 'DEEPSEEK_TIMEOUT_SEC' in cfg:
        os.environ['DEEPSEEK_TIMEOUT_SEC'] = str(cfg.get('DEEPSEEK_TIMEOUT_SEC') or '')
    if 'DEEPSEEK_MAX_RETRIES' in cfg:
        os.environ['DEEPSEEK_MAX_RETRIES'] = str(cfg.get('DEEPSEEK_MAX_RETRIES') or '')
    # Ollama
    if 'OLLAMA_HOST' in cfg:
        os.environ['OLLAMA_HOST'] = str(cfg.get('OLLAMA_HOST') or '')
    if 'OLLAMA_MODEL' in cfg:
        os.environ['OLLAMA_MODEL'] = str(cfg.get('OLLAMA_MODEL') or '')
    if 'USE_OLLAMA' in cfg:
        os.environ['USE_OLLAMA'] = str(cfg.get('USE_OLLAMA') or '')
    # App meta
    if 'APP_VERSION' in cfg:
        os.environ['APP_VERSION'] = str(cfg.get('APP_VERSION') or '')
    # SMS providers
    if 'SMS_IR_API_KEY' in cfg:
        os.environ['SMS_IR_API_KEY'] = str(cfg.get('SMS_IR_API_KEY') or '')
    if 'SMS_IR_TEMPLATE_ID' in cfg:
        os.environ['SMS_IR_TEMPLATE_ID'] = str(cfg.get('SMS_IR_TEMPLATE_ID') or '')
    if 'SMS_IR_VERIFY_URL' in cfg:
        os.environ['SMS_IR_VERIFY_URL'] = str(cfg.get('SMS_IR_VERIFY_URL') or '')
    if 'SMS_IR_PARAM_NAME' in cfg:
        os.environ['SMS_IR_PARAM_NAME'] = str(cfg.get('SMS_IR_PARAM_NAME') or '')
    if 'SMS_API_URL' in cfg:
        os.environ['SMS_API_URL'] = str(cfg.get('SMS_API_URL') or '')
    if 'SMS_API_KEY' in cfg:
        os.environ['SMS_API_KEY'] = str(cfg.get('SMS_API_KEY') or '')
    if 'SMS_SENDER' in cfg:
        os.environ['SMS_SENDER'] = str(cfg.get('SMS_SENDER') or '')


@app.context_processor
def _inject_globals():
    ver = os.getenv('APP_VERSION', APP_VERSION) or APP_VERSION
    return {
        'APP_VERSION': ver,
        'current_user': getattr(g, 'current_user', None),
    }


def _normalize_text(s: str) -> str:
    if not s:
        return ''
    s = s.lower()
    # remove zero-width chars and punctuation-like
    s = re.sub(r"[\u200c\u200f\u200e\ufeff]", "", s)
    return s


def _normalize_for_match(s: str) -> str:
    s = _normalize_text(s)
    s = s.replace('ي', 'ی').replace('ك', 'ک')
    s = s.replace('می ', 'می')
    s = s.replace('مي', 'می')
    return s


def _is_complaint_action_request(question: str) -> bool:
    q = _normalize_for_match(question or '')
    if not q:
        return False
    direct_patterns = [
        r'می ?خوام شکایت کنم',
        r'می‌خوام شکایت کنم',
        r'چطور شکایت کنم',
        r'چگونه شکایت کنم',
        r'چجور شکایت کنم',
        r'میخواهم شکایت کنم',
        r'طرح شکایت',
        r'دادخواست .*چطور',
        r'دادخواست .*چیکار',
    ]
    for pat in direct_patterns:
        if re.search(pat, q):
            return True
    if 'شکایت' in q or 'دادخواست' in q:
        action_tokens = ['چیکار', 'چی کار', 'چه کار', 'چطور', 'چگونه', 'چجوری', 'چی کنم', 'چه کنم', 'باید', 'الان']
        if any(tok.replace(' ', '') in q.replace(' ', '') for tok in action_tokens):
            return True
    return False


def _tokenize(text: str) -> List[str]:
    text = _normalize_text(text)
    return re.findall(r"[\w\d\u0600-\u06FF]+", text)


def _split_paragraphs(text: str) -> List[str]:
    # split by blank lines, then trim and keep reasonable chunks
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or '') if p and p.strip()]
    out: List[str] = []
    for p in parts:
        if len(p) >= 60:
            out.append(p)
    return out


def _rebuild_index(paragraphs: List[str]) -> Dict[str, Set[int]]:
    inv: Dict[str, Set[int]] = {}
    for i, p in enumerate(paragraphs):
        for tok in set(_tokenize(p)):
            s = inv.get(tok)
            if s is None:
                s = set()
                inv[tok] = s
            s.add(i)
    return inv
def _get_client_id() -> str:
    """Deterministic client id from IP + User-Agent; fallback to cookie if present.
    Stable across refresh/restart and differentiates devices behind same network.
    """
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
        import hashlib
        fp = f"{ip}|{ua}".encode('utf-8', 'ignore')
        h = hashlib.sha256(fp).hexdigest()[:24]
        return f"ipua_{h}"
    except Exception:
        return uuid.uuid4().hex


def _get_current_plan_limits() -> Tuple[int, int]:
    """Return (limit, window_sec) based on authenticated user's plan; fallback to env defaults.
    Plans: free, plus, pro, team
    """
    try:
        u = getattr(g, 'current_user', None) or {}
        plan = (u.get('plan') or 'free').strip().lower()
    except Exception:
        plan = 'free'
    # Base window sec from env or default
    try:
        base_window = int(os.getenv('RATE_WINDOW_SEC', str(RATE_WINDOW_SEC)))
    except Exception:
        base_window = RATE_WINDOW_SEC
    # Per-plan ask limits per window
    plan_limits = {
        'free': 8,
        'plus': 20,
        'pro': 60,
        'team': 120,
    }
    limit = int(plan_limits.get(plan, plan_limits['free']))
    return max(1, limit), max(10, base_window)


def _plan_storage_quota_bytes() -> int:
    """Per-user storage quota in bytes based on plan.
    free: 10 MB, plus: 100 MB, pro: 500 MB, team: 1 GB
    """
    try:
        u = getattr(g, 'current_user', None) or {}
        plan = (u.get('plan') or 'free').strip().lower()
    except Exception:
        plan = 'free'
    # admin-configurable quotas (bytes) in data/config.json: { QUOTA_FREE_MB, QUOTA_PLUS_MB, QUOTA_PRO_MB, QUOTA_TEAM_MB }
    cfg = _read_config()
    def mb(key, default_mb):
        try:
            return int(float(cfg.get(key, default_mb)) * 1024 * 1024)
        except Exception:
            return default_mb * 1024 * 1024
    table = {
        'free': mb('QUOTA_FREE_MB', 10),
        'plus': mb('QUOTA_PLUS_MB', 100),
        'pro': mb('QUOTA_PRO_MB', 500),
        'team': mb('QUOTA_TEAM_MB', 1024),
    }
    return int(table.get(plan, table['free']))


def _append_session(cid: str, role: str, text: str) -> None:
    if not cid or not text:
        return
    arr = SESSION_CTX.get(cid) or []
    arr.append({'role': role, 'text': text})
    # keep last 20 turns
    if len(arr) > 20:
        arr = arr[-20:]
    SESSION_CTX[cid] = arr


def _require_admin_if_configured():
    if not ADMIN_TOKEN:
        return None  # no protection configured
    provided = (
        request.headers.get('X-Admin-Token')
        or request.headers.get('X-Token')
    )
    if not provided or provided.strip() != ADMIN_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    return None


def _detect_intent_domain(question: str) -> Dict[str, str]:
    q = _normalize_text(question)
    
    # If DeepSeek is available, use AI for better intent detection
    if _should_use_deepseek():
        try:
            prompt = f"""تحلیل کن این سوال کاربر و intent و domain رو مشخص کن.
فقط یک JSON برگردون بدون توضیح اضافی:

Intent ها:
- login: کاربر میخواد وارد بشه، ثبت نام کنه، اکانت بسازه
- signup: کاربر میخواد عضو بشه، حساب کاربری بسازه
- advice: درخواست مشاوره حقوقی
- document: درخواست تهیه سند یا دادخواست
- analysis: تحلیل پرونده یا وضعیت
- qa: سوال و جواب عمومی

Domain ها:
- family: حقوق خانواده (طلاق، نفقه، حضانت، مهریه)
- criminal: حقوق کیفری (سرقت، کلاهبرداری)
- commerce: حقوق تجاری (قرارداد، شرکت، چک)
- property: حقوق املاک
- general: عمومی

سوال کاربر: "{question}"

پاسخ (فقط JSON):"""
            
            api_key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
            model = (os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat')
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 100
            }
            
            resp = requests.post(
                'https://api.deepseek.com/chat/completions',
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                ai_response = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                # Try to parse JSON from response
                import json
                import re
                # Extract JSON from markdown code blocks if present
                json_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', ai_response)
                if json_match:
                    ai_response = json_match.group(1)
                # Try direct JSON parse
                try:
                    result = json.loads(ai_response)
                    if 'intent' in result and 'domain' in result:
                        return {
                            'domain': result['domain'],
                            'intent': result['intent']
                        }
                except:
                    pass
        except Exception:
            pass  # Fall back to keyword-based detection
    
    # Fallback: keyword-based detection
    domains = {
        'family': ['نفقه', 'طلاق', 'حضانت', 'مهریه', 'ازدواج', 'خانواده'],
        'criminal': ['کیفری', 'سرقت', 'کلاهبرداری', 'ضرب و جرح', 'جرم'],
        'commerce': ['قرارداد', 'شرکت', 'تجارت', 'چک', 'اسناد تجاری'],
        'property': ['تصرف', 'ملک', 'پلاک', 'رفع تصرف', 'عدوانی', 'املاک'],
    }
    intents = {
        'login': ['ورود', 'وارد شوم', 'لاگین', 'login', 'sign in', 'دخول'],
        'signup': ['ثبت نام', 'عضویت', 'حساب کاربری', 'اکانت', 'signup', 'register', 'ثبتنام'],
        'advice': ['مشاوره', 'راهکار', 'چه کنم', 'قانون', 'توصیه'],
        'document': ['دادخواست', 'لایحه', 'درخواست', 'تنظیم', 'نمونه'],
        'analysis': ['تحلیل', 'ارزیابی', 'نتیجه', 'شانس', 'ریسک'],
    }
    domain_pick = 'general'
    intent_pick = 'qa'
    for d, kws in domains.items():
        if any(k in q for k in kws):
            domain_pick = d
            break
    for i, kws in intents.items():
        if any(k in q for k in kws):
            intent_pick = i
            break
    return {'domain': domain_pick, 'intent': intent_pick}


def _check_rate_limit(key: str, limit: int, window_sec: int) -> Tuple[bool, int]:
    now = time.time()
    arr = RATE_STATE.get(key) or []
    # drop old
    arr = [t for t in arr if (now - t) <= window_sec]
    allowed = len(arr) < limit
    if allowed:
        arr.append(now)
    RATE_STATE[key] = arr
    remaining = max(0, limit - len(arr))
    return allowed, remaining


def _should_use_deepseek() -> bool:
    flag = str(os.getenv('USE_DEEPSEEK', '')).strip().lower()
    key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
    if flag in ('0', 'false', 'no', 'off'):
        return False
    if flag in ('1', 'true', 'yes', 'on'):
        return bool(key)
    # Default behavior: enable if a key is present
    return bool(key)


_OPENAI_CLIENT = None
_OPENAI_CLIENT_SIG = ''


def _reset_openai_client() -> None:
    global _OPENAI_CLIENT, _OPENAI_CLIENT_SIG
    _OPENAI_CLIENT = None
    _OPENAI_CLIENT_SIG = ''


def _get_openai_client():
    """Return a persistent OpenAI client configured for DeepSeek with keep-alive."""
    global _OPENAI_CLIENT, _OPENAI_CLIENT_SIG
    key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
    base = (os.getenv('DEEPSEEK_BASE_URL', '').strip() or 'https://api.deepseek.com').rstrip('/')
    if not base.endswith('/v1'):
        base = base + '/v1'
    sig = f"{key}:{base}:{DEEPSEEK_TIMEOUT_SEC}"
    if _OPENAI_CLIENT is not None and _OPENAI_CLIENT_SIG == sig:
        return _OPENAI_CLIENT
    from openai import OpenAI
    app.logger.info(f"creating OpenAI client base={base}")
    client = OpenAI(api_key=key, base_url=base, timeout=DEEPSEEK_TIMEOUT_SEC)
    _OPENAI_CLIENT = client
    _OPENAI_CLIENT_SIG = sig
    return client


def _deepseek_chat(question: str, context: str, thinking_time: int = 0, role: str = 'default', case_info: dict = None) -> Tuple[bool, str]:
    """Call DeepSeek via OpenAI SDK with retries; returns (ok, text_or_error).
    
    Args:
        question: The user's question
        context: RAG context from documents
        thinking_time: Time in seconds for deep thinking (0, 15, 30, 60)
        role: The role to adopt (default, lawyer, judge)
        case_info: Case information for lawyer role (optional)
    """
    key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
    if not key:
        return False, 'DEEPSEEK_API_KEY not set'
    model = (os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat')
    
    # Base system prompts for different roles
    role_prompts = {
        'default': 'شما یک دستیار حقوقی فارسی هستید.',
        'lawyer': '''شما «دادرس هوشمند» هستید؛ وکیل پایه یک دادگستری و همراه وفادار موکل.

🎓 شخصیت شما:
- حافظ منافع موکل و همراه مرحله‌به‌مرحله او
- دقیق، دلسوز و قاطع در مسیر دادرسی
- تمرکز کامل روی پرونده فعلی و جزئیات آن
- زبان حرفه‌ای، صمیمی و قابل فهم برای موکل

⚖️ سبک پاسخ:
- تحلیل از دیدگاه دفاعی یا حمایتی متناسب با نقش موکل
- شناسایی نقاط قوت و هشدار نسبت به ریسک‌ها
- ارائه نقشه راه مرحله‌به‌مرحله برای رسیدن به نتیجه مطلوب
- هر پاسخ باید حداقل شامل سه بخش باشد: «ارزیابی کوتاه وضعیت»، «اقدامات یا توصیه‌های عملی»، «یادآوری گام بعدی»
- در پایان، از موکل بخواه که اقدام مشخصی انجام دهد یا تایید کند

🚫 محدودیت‌ها:
- فقط درباره همین پرونده، اطلاعات آن و روند دادرسی صحبت کن
- اگر سوال کاربر ارتباطی با این پرونده ندارد یا خارج از مسیر رسیدگی است، پاسخ نده و کوتاه بگو: «این پرسش خارج از محدودهٔ این پرونده است؛ لطفاً برای موضوعات دیگر یک چت جدید باز کنید.»
- از ارائه مشاوره کلی یا خارج از حوزه پرونده فعلی خودداری کن''',
        'judge': '''شما یک قاضی باتجربه دادگاه عمومی هستید.

⚖️ شخصیت شما:
- بی‌طرف و عادل
- تحلیل از دیدگاه قانون
- دقت در اصول و رویه
- زبان رسمی و قضایی

👨‍⚖️ سبک پاسخ:
- تحلیل حقوقی کامل
- بررسی دو طرف پرونده
- استناد دقیق به قوانین و رویه قضایی
- پیش‌بینی رأی احتمالی دادگاه
- توضیح استدلال‌های حقوقی'''
    }
    
    base_system = role_prompts.get(role, role_prompts['default'])
    
    # Adjust system prompt based on thinking time
    if thinking_time > 0:
        system = f'''{base_system}

⏰ زمان تحلیل: {thinking_time} ثانیه

🎯 راهنمای فکر عمیق:
1. ابتدا سوال را به دقت تحلیل کن
2. تمام جنبه‌های حقوقی مرتبط را بررسی کن
3. قوانین و مواد مربوطه را شناسایی کن
4. به استنادات موجود در زمینه دقت کن
5. پاسخ جامع و مستند ارائه ده

📚 پاسخ باید:
- جامع و کامل باشد
- دارای استناد به قوانین باشد
- جنبه‌های مختلف مسئله را پوشش دهد
- پیشنهادات عملی داشته باشد
- به زبان ساده و قابل فهم باشد'''
    else:
        system = base_system + ' پاسخ کوتاه، دقیق و مستند بده.'
    
    # اضافه کردن اطلاعات پرونده به prompt برای وکیل
    case_context = ''
    if case_info and role == 'lawyer':
        case_context = '\n\n[اطلاعات پرونده فعلی]\n'
        if case_info.get('client_name'):
            case_context += f"موکل: {case_info['client_name']}\n"
        if case_info.get('case_type'):
            case_context += f"نوع پرونده: {case_info['case_type']}\n"
        if case_info.get('opponent_name'):
            case_context += f"طرف مقابل: {case_info['opponent_name']}\n"
        if case_info.get('case_stage'):
            case_context += f"مرحله: {case_info['case_stage']}\n"
        if case_info.get('case_number'):
            case_context += f"شماره پرونده: {case_info['case_number']}\n"
        if case_info.get('case_goal'):
            case_context += f"هدف: {case_info['case_goal']}\n"
        if case_info.get('incident_description'):
            case_context += f"شرح ماجرا: {case_info['incident_description'][:300]}\n"
        history = case_info.get('conversation_history') or []
        if history:
            case_context += '\n[خلاصه مکالمه اخیر]\n'
            recent = history[-12:]
            for idx, item in enumerate(recent, start=max(1, len(history) - len(recent) + 1)):
                text = (item.get('text') or '').strip()
                if not text:
                    continue
                speaker = 'موکل' if item.get('role') == 'user' else 'دادرس'
                case_context += f"{speaker} {idx}: {text[:320]}\n"
            case_context += '---\nلطفاً ادامه همین گفتگو را با توجه به پیام‌های بالا پیش ببر.\n'
        case_context += '\n⚠️ فقط درباره همین پرونده پاسخ بده و اگر سوال خارج از این محدوده بود مودبانه موکل را به ایجاد چت جدید راهنمایی کن.'
    
    user = f"[زمینه]\n{context}\n\n[سؤال]\n{question}{case_context}"
    try:
        client = _get_openai_client()
    except Exception as exc:
        return False, f'OpenAI client error: {exc}'

    last_error = ''
    for attempt in range(max(1, DEEPSEEK_MAX_RETRIES)):
        try:
            # Adjust max_tokens based on thinking time
            max_tokens = 512
            if thinking_time >= 60:
                max_tokens = 2048
            elif thinking_time >= 30:
                max_tokens = 1024
            elif thinking_time >= 15:
                max_tokens = 768
            
            # Adjust timeout based on thinking time
            timeout = max(DEEPSEEK_TIMEOUT_SEC, thinking_time + 30)
            
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=False,
                max_tokens=max_tokens,
                timeout=timeout,
                temperature=0.7 if thinking_time > 0 else 0.3,
            )
            text = (resp.choices[0].message.content or '').strip()
            return (True, text)
        except Exception as exc:
            last_error = str(exc)
            app.logger.warning(f"deepseek attempt={attempt+1} error={last_error}")
            if attempt < DEEPSEEK_MAX_RETRIES - 1:
                # small exponential backoff to smooth transient network issues
                try:
                    time.sleep(min(5.0, 0.5 * (2 ** attempt)))
                except Exception:
                    pass
            else:
                break
    return False, f'DeepSeek(OpenAI) error after retries: {last_error}'


def _ingest_directory(dir_path: str, recursive: bool = True) -> Tuple[int, int]:
    """Return (files_loaded, paragraphs_added). Load .txt and .pdf files."""
    files_loaded = 0
    paragraphs_added = 0
    if not os.path.isdir(dir_path):
        return 0, 0

    def iter_txt(p: str):
        if recursive:
            for root, _dirs, files in os.walk(p):
                for name in files:
                    if name.lower().endswith('.txt'):
                        yield os.path.join(root, name)
        else:
            for name in os.listdir(p):
                fp = os.path.join(p, name)
                if os.path.isfile(fp) and name.lower().endswith('.txt'):
                    yield fp

    def iter_pdf(p: str):
        if recursive:
            for root, _dirs, files in os.walk(p):
                for name in files:
                    if name.lower().endswith('.pdf'):
                        yield os.path.join(root, name)
        else:
            for name in os.listdir(p):
                fp = os.path.join(p, name)
                if os.path.isfile(fp) and name.lower().endswith('.pdf'):
                    yield fp

    global LOADED_FILES, PARAGRAPHS, INVERTED
    # 1) ingest txt
    for fp in iter_txt(dir_path):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        if not content:
            continue
        paras = _split_paragraphs(content)
        if not paras:
            continue
        base = len(PARAGRAPHS)
        PARAGRAPHS.extend(paras)
        if len(PAR_SOURCE) < base:
            PAR_SOURCE.extend([''] * (base - len(PAR_SOURCE)))
        PAR_SOURCE.extend([fp] * len(paras))
        files_loaded += 1
        paragraphs_added += len(paras)
        LOADED_FILES.append(fp)
    # 2) ingest pdf (try text; fallback OCR)
    for fp in iter_pdf(dir_path):
        content = ''
        # fast text extraction by pdfminer
        try:
            from pdfminer.high_level import extract_text as _pdf_extract
            content = (_pdf_extract(fp) or '').strip()
        except Exception:
            content = ''
        # fallback: OCR via PyMuPDF + Tesseract
        if not content:
            try:
                import fitz  # PyMuPDF
                from PIL import Image
                import pytesseract
                doc = fitz.open(fp)
                parts: List[str] = []
                m = fitz.Matrix(2, 2)
                for page in doc:
                    pix = page.get_pixmap(matrix=m)
                    mode = 'RGB' if pix.alpha == 0 else 'RGBA'
                    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                    try:
                        txt = pytesseract.image_to_string(img, lang='fas+eng')
                    except Exception:
                        txt = pytesseract.image_to_string(img)
                    if txt:
                        parts.append(txt)
                content = '\n'.join(parts).strip()
            except Exception:
                content = ''
        if not content:
            continue
        # persist extracted text as .txt next to the PDF
        try:
            _ensure_data_dirs()
            out_path = os.path.splitext(fp)[0] + '.txt'
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass

        paras = _split_paragraphs(content)
        if not paras:
            continue
        base = len(PARAGRAPHS)
        PARAGRAPHS.extend(paras)
        if len(PAR_SOURCE) < base:
            PAR_SOURCE.extend([''] * (base - len(PAR_SOURCE)))
        PAR_SOURCE.extend([fp] * len(paras))
        files_loaded += 1
        paragraphs_added += len(paras)
        LOADED_FILES.append(fp)
    INVERTED = _rebuild_index(PARAGRAPHS)
    return files_loaded, paragraphs_added


def _iter_pdfs(dir_path: str, recursive: bool = True):
    if recursive:
        for root, _dirs, files in os.walk(dir_path):
            for name in files:
                if name.lower().endswith('.pdf'):
                    yield os.path.join(root, name)
    else:
        for name in os.listdir(dir_path):
            fp = os.path.join(dir_path, name)
            if os.path.isfile(fp) and name.lower().endswith('.pdf'):
                yield fp


def _extract_pdf_text_to_file(fp: str, force: bool = False) -> Tuple[bool, str]:
    """Extract text from a single PDF and save as .txt next to it. Returns (saved, path_or_error)."""
    try:
        out_path = os.path.splitext(fp)[0] + '.txt'
        if (not force) and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return (False, out_path)
        # try text
        text = ''
        try:
            from pdfminer.high_level import extract_text as _pdf_extract
            text = (_pdf_extract(fp) or '').strip()
        except Exception:
            text = ''
        if not text:
            try:
                import fitz
                from PIL import Image
                import pytesseract
                doc = fitz.open(fp)
                parts: List[str] = []
                m = fitz.Matrix(2, 2)
                for page in doc:
                    pix = page.get_pixmap(matrix=m)
                    mode = 'RGB' if pix.alpha == 0 else 'RGBA'
                    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                    try:
                        txt = pytesseract.image_to_string(img, lang='fas+eng')
                    except Exception:
                        txt = pytesseract.image_to_string(img)
                    if txt:
                        parts.append(txt)
                text = '\n'.join(parts).strip()
            except Exception:
                text = ''
        if not text:
            return (False, 'no_text')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return (True, out_path)
    except Exception as exc:
        return (False, f'error: {exc}')


@app.post('/admin/extract-pdf-text')
def admin_extract_pdf_text():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    data = request.get_json(silent=True) or {}
    dir_path = data.get('dir') or os.path.join(DATA_DIR, 'texts')
    recursive = bool(data.get('recursive', True))
    force = bool(data.get('force', False))
    if not os.path.isdir(dir_path):
        return jsonify({'ok': False, 'error': 'dir_not_exists'}), 400
    total = 0
    saved = 0
    skipped = 0
    errors = 0
    outputs: List[str] = []
    for fp in _iter_pdfs(dir_path, recursive=recursive):
        total += 1
        ok, info = _extract_pdf_text_to_file(fp, force=force)
        if ok:
            saved += 1
            outputs.append(info)
        else:
            if info == 'no_text':
                skipped += 1
            elif info.endswith('.txt'):
                skipped += 1
            else:
                errors += 1
    return jsonify({'ok': True, 'dir': os.path.abspath(dir_path), 'total_pdfs': total, 'saved': saved, 'skipped': skipped, 'errors': errors, 'outputs': outputs[:50]})


@app.get('/healthz')
def health():
    return 'ok', 200


@app.get('/')
def index():
    # If a template exists, render it; otherwise minimal HTML
    tpl_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    cid = _get_client_id()
    if os.path.exists(tpl_path):
        html = render_template('index.html')
        resp = make_response(html)
        if not request.cookies.get('client_id'):
            resp.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
        return resp
    html = '<h1>Dadras – Minimal</h1><p>It works.</p>'
    resp = make_response(html)
    if not request.cookies.get('client_id'):
        resp.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return resp


# Friendly chat URL: /c/<chat_id> → same UI, JS picks ID from URL
@app.get('/c/<chat_id>')
def chat_shortlink(chat_id: str):
    tpl_path = os.path.join(BASE_DIR, 'templates', 'index.html')
    cid = _get_client_id()
    if os.path.exists(tpl_path):
        html = render_template('index.html')
        resp = make_response(html)
        if not request.cookies.get('client_id'):
            resp.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
        return resp
    return index()


@app.get('/case/<case_id>')
def case_shortlink(case_id: str):
    return chat_shortlink(case_id)

# Notes routes moved to routes/notes.py blueprint

@app.post('/ingest')
def ingest_endpoint():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    _ensure_data_dirs()
    data = request.get_json(silent=True) or {}
    dir_path = data.get('dir') or os.path.join(DATA_DIR, 'texts')
    recursive = bool(data.get('recursive', True))
    files_loaded, paragraphs_added = _ingest_directory(dir_path, recursive=recursive)
    return jsonify({
        'dir': os.path.abspath(dir_path),
        'files_loaded': files_loaded,
        'paragraphs_added': paragraphs_added,
        'total_paragraphs': len(PARAGRAPHS)
    })


@app.post('/ingest-texts')
def ingest_texts_endpoint():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    _ensure_data_dirs()
    dir_path = os.path.join(DATA_DIR, 'texts')
    files_loaded, paragraphs_added = _ingest_directory(dir_path, recursive=True)
    return jsonify({
        'dir': os.path.abspath(dir_path),
        'files_loaded': files_loaded,
        'paragraphs_added': paragraphs_added,
        'total_paragraphs': len(PARAGRAPHS)
    })


def _retrieve(question: str, top_k: int = 5) -> List[Dict[str, object]]:
    if not question:
        return []
    if not PARAGRAPHS or not INVERTED:
        return []
    q_tokens = set(_tokenize(question))
    if not q_tokens:
        return []
    scores: Dict[int, int] = {}
    for qt in q_tokens:
        for pid in INVERTED.get(qt, set()):
            scores[pid] = scores.get(pid, 0) + 1
    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max(1, int(top_k))]
    out: List[Dict[str, object]] = []
    for pid, sc in ranked:
        snippet = PARAGRAPHS[pid]
        src = ''
        try:
            src = PAR_SOURCE[pid]
        except Exception:
            src = ''
        out.append({'pid': int(pid), 'score': int(sc), 'snippet': snippet, 'source': src})
    return out


@app.post('/case/analyze')
def case_analyze():
    """
    تحلیل کامل وضعیت پرونده و ارائه راهنمایی
    """
    try:
        from routes.case_manager import CaseManager
        
        data = request.get_json(silent=True) or {}
        case_info = data.get('case_info', {})
        
        manager = CaseManager()
        analysis = manager.analyze_case_status(case_info)
        next_actions = manager.suggest_next_actions(case_info, analysis)
        checklist = manager.generate_checklist(analysis['current_stage_key'], case_info)
        
        return jsonify({
            'ok': True,
            'analysis': analysis,
            'next_actions': next_actions,
            'checklist': checklist
        })
    except Exception as e:
        app.logger.error(f"Error in case analyze: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.post('/case/generate-document')
def case_generate_document():
    """
    تولید اسناد حقوقی (دادخواست، لایحه، دفاعیه)
    """
    try:
        from routes.case_manager import CaseManager
        
        data = request.get_json(silent=True) or {}
        doc_type = data.get('doc_type', 'lawsuit')
        case_info = data.get('case_info', {})
        additional_info = data.get('additional_info', {})
        
        manager = CaseManager()
        document_result = manager.generate_document(doc_type, case_info, additional_info)

        if isinstance(document_result, dict):
            document_text = document_result.get('text', '')
            instructions = document_result.get('instructions', '')
            stage_key = document_result.get('stage_key')
            stage_label = document_result.get('stage_label')
            doc_label = document_result.get('doc_label')
            case_title = document_result.get('case_title')
            needs_info = bool(document_result.get('needs_info'))
            missing_fields = document_result.get('missing_fields') or []
        else:
            document_text = str(document_result)
            instructions = ''
            stage_key = None
            stage_label = None
            doc_label = None
            case_title = None
            needs_info = False
            missing_fields = []
        
        return jsonify({
            'ok': True,
            'document': document_text,
            'doc_type': doc_type,
            'instructions': instructions,
            'stage_key': stage_key,
            'stage_label': stage_label,
            'doc_label': doc_label,
            'case_title': case_title,
            'needs_info': needs_info,
            'missing_fields': missing_fields
        })
    except Exception as e:
        app.logger.error(f"Error in generate document: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.post('/api/extract-case-info')
def extract_case_info():
    """
    استخراج خودکار اطلاعات پرونده از پیام‌های AI
    """
    try:
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
        current_info = data.get('current_info', {})
        
        if not message:
            return jsonify({'ok': False, 'error': 'پیام خالی است'}), 400
        
        # استفاده از AI برای استخراج اطلاعات
        prompt = f"""از متن زیر، اطلاعات پرونده حقوقی را استخراج کن و در فرمت JSON برگردان.
فقط اطلاعات جدیدی که در متن ذکر شده را برگردان (نه همه فیلدها).

متن: {message}

اطلاعات فعلی پرونده:
{_json.dumps(current_info, ensure_ascii=False, indent=2)}

فرمت JSON خروجی (فقط فیلدهای جدید):
{{
  "client_name": "نام موکل",
  "opponent_name": "نام طرف مقابل",
  "case_stage": "مرحله پرونده",
  "case_number": "شماره پرونده",
  "case_goal": "هدف پرونده",
  "available_documents": "مدارک موجود",
  "complaint_side": "plaintiff یا defendant یا unknown"
}}

اگر اطلاعات جدیدی در متن نیست، یک JSON خالی برگردان: {{}}
فقط JSON برگردان، بدون توضیح اضافی."""
        
        import os
        import requests
        
        api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
        if not api_key:
            return jsonify({'ok': False, 'error': 'API key not configured'}), 500
        
        model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
        base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip()
        
        if not base_url.endswith('/v1'):
            base_url = base_url.rstrip('/') + '/v1'
        
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 500
            },
            timeout=15
        )
        
        if response.status_code == 200:
            ai_data = response.json()
            ai_response = ai_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # پارس JSON
            try:
                # حذف markdown code blocks اگر وجود داشت
                if '```json' in ai_response:
                    ai_response = ai_response.split('```json')[1].split('```')[0].strip()
                elif '```' in ai_response:
                    ai_response = ai_response.split('```')[1].split('```')[0].strip()
                
                extracted_info = _json.loads(ai_response)
                
                # ادغام با اطلاعات فعلی
                updated_info = {**current_info, **extracted_info}
                
                return jsonify({
                    'ok': True,
                    'extracted_info': updated_info
                })
            except _json.JSONDecodeError as e:
                app.logger.error(f"JSON parse error: {e}, Response: {ai_response}")
                return jsonify({'ok': False, 'error': 'خطا در پارس اطلاعات'}), 500
        else:
            return jsonify({'ok': False, 'error': 'خطا در ارتباط با AI'}), 500
            
    except Exception as e:
        app.logger.error(f"Error extracting case info: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@app.post('/case/conversation/next')
def case_conversation_next():
    """
    دریافت سوال بعدی در گفتگوی جمع‌آوری اطلاعات پرونده
    """
    try:
        from routes.case_conversation import CaseConversationManager
        from routes.case_manager import CaseManager
        
        data = request.get_json(silent=True) or {}
        case_id = data.get('case_id', '')
        case_title = data.get('case_title', '')
        case_type = data.get('case_type', 'other')
        case_info = data.get('case_info', {})
        conversation_history = data.get('conversation_history', [])
        user_answer = data.get('user_answer', '')
        current_question_id = data.get('current_question_id')
        lawyer_name = data.get('lawyer_name')
        
        manager = CaseConversationManager()
        
        # اگر پاسخ کاربر وجود دارد، استخراج اطلاعات
        if user_answer and current_question_id:
            # پیدا کردن فیلدهای مورد نظر
            current_q = None
            for q in manager.questions_flow:
                if q['id'] == current_question_id:
                    current_q = q
                    break
            
            if current_q:
                case_info = manager.extract_info_from_answer(
                    user_answer,
                    current_q['extract'],
                    case_info
                )
        
        # دریافت سوال بعدی (حالت چت)
        question_text, question_id, is_complete, chat_ack = manager.get_next_question(
            case_info,
            conversation_history,
            case_title,
            lawyer_name
        )
        
        if is_complete:
            # تشخیص خودکار نوع پرونده با AI
            detected_type = manager.detect_case_type_with_ai(case_info)
            case_info['case_type'] = detected_type
            
            # تکمیل گفتگو و ارسال خلاصه
            summary = manager.finalize_case_info(case_info, detected_type)
            
            # تولید خلاصه با AI (اگر ممکن باشد)
            ai_summary = manager.generate_ai_summary(summary)
            
            # اگر AI خلاصه تولید نکرد، از خلاصه معمولی استفاده کن
            if ai_summary:
                summary_text = ai_summary
            else:
                summary_text = manager.generate_summary_text(summary)
            
            # تولید راهنمای مرحله‌به‌مرحله و سوالات تکمیلی
            step_guidance = None
            try:
                case_manager = CaseManager()
                step_guidance = case_manager.generate_step_by_step_guidance(case_info)
            except Exception as guidance_error:
                app.logger.error(f"Error generating step guidance: {guidance_error}")
                step_guidance = None

            smart_questions = manager.get_smart_questions(case_info)
            
            return jsonify({
                'ok': True,
                'complete': True,
                'summary': summary,
                'summary_text': summary_text,
                'case_info': case_info,
                'detected_type': detected_type,
                'smart_questions': smart_questions,
                'step_guidance': step_guidance,
                'next_step': 'comprehensive_analysis'  # راهنمایی برای مرحله بعد
            })
        else:
            return jsonify({
                'ok': True,
                'complete': False,
                'question': question_text,
                'question_id': question_id,
                'case_info': case_info
            })
            
    except Exception as e:
        app.logger.error(f"Error in case conversation: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@app.post('/case/comprehensive-analysis')
def case_comprehensive_analysis():
    """
    تحلیل جامع و یکپارچه پرونده با تمام قابلیت‌ها
    
    این endpoint تحلیل کاملی از پرونده ارائه می‌دهد شامل:
    - تحلیل وضعیت فعلی
    - تحلیل هوشمند با AI
    - تشخیص قوانین مرتبط
    - پیش‌بینی نتایج
    - پیشنهاد اقدامات
    - سوالات تکمیلی
    """
    try:
        from routes.case_manager import CaseManager
        from routes.case_conversation import CaseConversationManager
        
        data = request.get_json(silent=True) or {}
        case_info = data.get('case_info', {})
        include_ai = data.get('include_ai', True)  # استفاده از AI یا خیر
        
        if not case_info:
            return jsonify({'ok': False, 'error': 'اطلاعات پرونده ارسال نشده است'}), 400
        
        manager = CaseManager()
        conv_manager = CaseConversationManager()
        
        # 1. تحلیل پایه وضعیت پرونده
        base_analysis = manager.analyze_case_status(case_info)
        
        result = {
            'ok': True,
            'base_analysis': {
                'current_stage': base_analysis['current_stage'],
                'urgent_actions': base_analysis['urgent_actions'],
                'strategy': base_analysis['strategy'],
                'risks': base_analysis['risks'],
                'opportunities': base_analysis['opportunities'],
                'next_steps': base_analysis['next_steps'],
                'required_documents': base_analysis['required_documents']
            }
        }
        
        # 2. چک‌لیست اقدامات
        checklist = manager.generate_checklist(base_analysis['current_stage_key'], case_info)
        result['checklist'] = checklist
        
        # 3. پیشنهاد اقدامات بعدی
        next_actions = manager.suggest_next_actions(case_info, base_analysis)
        result['next_actions'] = next_actions
        
        laws = None
        step_guidance = None
        
        # اگر استفاده از AI فعال باشد
        if include_ai:
            # 4. تحلیل هوشمند با AI
            ai_analysis = manager.analyze_with_ai(case_info)
            if ai_analysis and ai_analysis.get('success'):
                result['ai_analysis'] = ai_analysis['ai_analysis']
            
            # 5. تشخیص قوانین مرتبط
            laws = manager.detect_relevant_laws(case_info)
            if laws and laws.get('success'):
                result['relevant_laws'] = laws['laws_text']
                result['laws_source'] = laws['source']
            
            # 6. پیش‌بینی نتایج
            prediction = manager.predict_outcome(case_info, base_analysis)
            if prediction and prediction.get('success'):
                result['outcome_prediction'] = prediction['prediction_text']
                result['prediction_score'] = prediction.get('score', 0)
                result['prediction_source'] = prediction['source']
            
            # 7. سوالات تکمیلی هوشمند
            smart_questions = conv_manager.get_smart_questions(case_info)
            result['smart_questions'] = smart_questions
        
        # راهنمای مرحله‌به‌مرحله (با استفاده از AI یا fallback)
        try:
            step_guidance = manager.generate_step_by_step_guidance(case_info, base_analysis, laws)
        except Exception as guidance_error:
            app.logger.error(f"Error generating step guidance (comprehensive): {guidance_error}")
            step_guidance = None

        if step_guidance:
            result['step_guidance'] = step_guidance

        # 8. خلاصه نهایی
        result['summary'] = {
            'case_title': case_info.get('case_title', ''),
            'case_type': case_info.get('case_type', ''),
            'stage': base_analysis['current_stage']['name'],
            'has_ai_analysis': include_ai and result.get('ai_analysis') is not None,
            'has_laws': include_ai and result.get('relevant_laws') is not None,
            'has_prediction': include_ai and result.get('outcome_prediction') is not None
        }
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in comprehensive analysis: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@app.post('/case/smart-questions')
def case_smart_questions():
    """
    دریافت سوالات تکمیلی هوشمند بر اساس اطلاعات پرونده
    """
    try:
        from routes.case_conversation import CaseConversationManager
        
        data = request.get_json(silent=True) or {}
        case_info = data.get('case_info', {})
        
        if not case_info:
            return jsonify({'ok': False, 'error': 'اطلاعات پرونده ارسال نشده است'}), 400
        
        manager = CaseConversationManager()
        questions = manager.get_smart_questions(case_info)
        
        return jsonify({
            'ok': True,
            'questions': questions
        })
        
    except Exception as e:
        app.logger.error(f"Error getting smart questions: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500


@app.post('/ask')
def ask_endpoint():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    case_info = data.get('case_info', {})
    try:
        top_k = int(data.get('top_k', 5))
    except Exception:
        top_k = 5
    try:
        thinking_time = int(data.get('thinking_time', 0))
        # Validate thinking_time is one of allowed values
        if thinking_time not in [0, 15, 30, 60]:
            thinking_time = 0
    except Exception:
        thinking_time = 0
    role = (data.get('role') or 'default').strip()
    # Validate role is one of allowed values
    if role not in ['default', 'lawyer', 'judge']:
        role = 'default'
    meta = _detect_intent_domain(question)
    cid = _get_client_id()
    # rate limit per client/ip with plan-based limits
    rl_key = (getattr(g, 'current_user', {}).get('id') if getattr(g, 'current_user', None) else None) or request.remote_addr or cid
    plan_limit, plan_window = _get_current_plan_limits()
    ok, remaining = _check_rate_limit(rl_key, plan_limit, plan_window)
    if not ok:
        return jsonify({'error': 'rate_limited', 'retry_in_sec': plan_window, 'limit': plan_limit}), 429
    _append_session(cid, 'user', question)

    if _is_complaint_action_request(question):
        try:
            from routes.case_manager import CaseManager
            manager = CaseManager()
            doc_result = manager.generate_document('lawsuit', case_info or {})
        except Exception as doc_error:
            app.logger.error(f"Error generating complaint document: {doc_error}")
            doc_result = {
                'text': 'امکان تولید دادخواست خودکار فراهم نشد؛ لطفاً با وکیل خود مشورت کنید.',
                'instructions': '',
                'stage_label': None,
            }

        if isinstance(doc_result, dict):
            doc_text = doc_result.get('text', '')
            instructions = doc_result.get('instructions', '')
            stage_label = doc_result.get('stage_label')
            missing_fields = doc_result.get('missing_fields') or []
            needs_info = bool(doc_result.get('needs_info'))
        else:
            doc_text = str(doc_result)
            instructions = ''
            stage_label = None
            missing_fields = []
            needs_info = False

        if needs_info:
            prompt_lines = []
            clarify_prompts = []
            for item in missing_fields:
                prompt = (item.get('prompt') or '').strip()
                field_title = item.get('field') or ''
                if prompt:
                    prompt_lines.append(f"• {prompt}")
                    clarify_prompts.append(prompt)
                elif field_title:
                    line = f"• {field_title} را مشخص کن."
                    prompt_lines.append(line)
                    clarify_prompts.append(line.replace('• ', ''))
            if not prompt_lines:
                prompt_lines.append('• جزئیات پرونده را کامل کن تا بتوانم دادخواست را تنظیم کنم.')

            answer_text = 'برای تنظیم دادخواست، ابتدا این اطلاعات را برایم ارسال کن:\n' + '\n'.join(prompt_lines)
            resp = jsonify({'answer': answer_text, 'citations': [], 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': clarify_prompts})
            r = make_response(resp)
            if not request.cookies.get('client_id'):
                r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
            return r

        message_parts = [
            '👣 برو دادسرای منطقه یا نزدیک‌ترین دفتر خدمات الکترونیک قضایی و این دادخواست را تقدیم کن.'
        ]
        if instructions:
            message_parts.append(instructions)
        if stage_label and stage_label not in {'', 'مرحله نامشخص'}:
            message_parts.append(f'🔎 مرحله پرونده تشخیص داده‌شده: {stage_label}')
        if doc_text:
            message_parts.append(doc_text)
        answer_text = '\n\n'.join([part for part in message_parts if part])

        resp = jsonify({'answer': answer_text, 'citations': [], 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': []})
        r = make_response(resp)
        if not request.cookies.get('client_id'):
            r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
        return r
    # Retrieve local snippets (RAG)
    results = _retrieve(question, top_k=top_k)
    citations = [
        {
            'pid': r['pid'],
            'score': r['score'],
            'snippet': r['snippet'][:400],
            'source': os.path.basename(r.get('source') or '')
        }
        for r in results
    ] if results else []
    rag_context = '\n\n---\n\n'.join([c['snippet'] for c in citations[:3]]) if citations else ''

    # If DeepSeek configured, prefer DeepSeek answer with RAG context
    if _should_use_deepseek():
        ok, ds_text = _deepseek_chat(question, rag_context, thinking_time, role, case_info)
        if ok and ds_text:
            resp = jsonify({'answer': ds_text, 'citations': citations, 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': []})
            r = make_response(resp)
            if not request.cookies.get('client_id'):
                r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
            return r
        else:
            # fall back to local with error hint
            fallback_note = f"(DeepSeek: {ds_text})" if ds_text else ''
            if not citations:
                resp = jsonify({'answer': f'پاسخی یافت نشد؛ لطفاً جزئیات بیشتری بدهید. {fallback_note}', 'citations': [], 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': ['موضوع دقیق', 'طرفین', 'تاریخ رویداد']})
                r = make_response(resp)
                if not request.cookies.get('client_id'):
                    r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
                return r
            picks = [c['snippet'] for c in citations][:max(1, min(top_k, 3))]
            answer = 'نتیجهٔ اولیه بر اساس متون یافت‌شده:\n\n' + ('\n\n---\n\n'.join(picks)) + (('\n\n' + fallback_note) if fallback_note else '')
            clarify = []
            max_score = max(int(c['score']) for c in citations) if citations else 0
            if max_score < 2:
                clarify = ['شرح دقیق‌تر مسئله', 'طرفین و رابطه حقوقی', 'تاریخ و مدارک موجود']
            resp = jsonify({'answer': answer, 'citations': citations, 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': clarify})
            r = make_response(resp)
            if not request.cookies.get('client_id'):
                r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
            return r

    # Local answer (no DeepSeek)
    if not citations:
        resp = jsonify({'answer': 'پاسخی یافت نشد؛ لطفاً جزئیات بیشتری بدهید.', 'citations': [], 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': ['موضوع دقیق', 'طرفین', 'تاریخ رویداد']})
        r = make_response(resp)
        if not request.cookies.get('client_id'):
            r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
        return r
    picks = [c['snippet'] for c in citations][:max(1, min(top_k, 3))]
    answer = 'نتیجهٔ اولیه بر اساس متون یافت‌شده:\n\n' + ('\n\n---\n\n'.join(picks))
    clarify = []
    max_score = max(int(c['score']) for c in citations) if citations else 0
    if max_score < 2:
        clarify = ['شرح دقیق‌تر مسئله', 'طرفین و رابطه حقوقی', 'تاریخ و مدارک موجود']
    resp = jsonify({'answer': answer, 'citations': citations, 'intent': meta['intent'], 'domain': meta['domain'], 'clarify': clarify})
    r = make_response(resp)
    if not request.cookies.get('client_id'):
        r.set_cookie('client_id', cid, max_age=30*24*3600, httponly=False, samesite='Lax')
    return r


@app.get('/admin/stats')
def admin_stats():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    cfg = _read_config()
    return jsonify({
        'files': len(LOADED_FILES),
        'paragraphs': len(PARAGRAPHS),
        'vocab': len(INVERTED),
        'data_dir': DATA_DIR,
        'log': {
            'file': CURRENT_LOG_FILE,
            'level': str(os.getenv('LOG_LEVEL', 'INFO')).upper().strip() or 'INFO',
        },
        'llm': {
            'use_deepseek': os.getenv('USE_DEEPSEEK', ''),
            'deepseek_model': os.getenv('DEEPSEEK_MODEL', ''),
            'deepseek_key_set': bool(os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY),
            'deepseek_base_url': os.getenv('DEEPSEEK_BASE_URL', ''),
            'deepseek_timeout_sec': os.getenv('DEEPSEEK_TIMEOUT_SEC', ''),
            'deepseek_max_retries': os.getenv('DEEPSEEK_MAX_RETRIES', ''),
            'use_ollama': os.getenv('USE_OLLAMA', ''),
            'ollama_host': os.getenv('OLLAMA_HOST', ''),
            'ollama_model': os.getenv('OLLAMA_MODEL', ''),
        },
        'config_exists': os.path.exists(CONFIG_PATH),
        'config': {k: ('***' if 'KEY' in k else v) for k, v in cfg.items()},
    })


@app.get('/templates')
def list_templates():
    _ensure_data_dirs()
    tpl_dir = os.path.join(DATA_DIR, 'templates')
    items = []
    try:
        for name in os.listdir(tpl_dir):
            if name.lower().endswith('.txt'):
                items.append(name)
    except Exception:
        items = []
    return jsonify({'templates': items})


@app.get('/admin/config')
def admin_get_config():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    cfg = _read_config()
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
    # explicit flags for UX
    masked['DEEPSEEK_API_KEY_SET'] = key_set
    if key_masked:
        masked['DEEPSEEK_API_KEY_MASKED'] = key_masked
    return jsonify(masked)


@app.post('/admin/config')
def admin_set_config():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'invalid_body'}), 400
    cfg = _read_config()
    allow = {
        'USE_DEEPSEEK', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL',
        'DEEPSEEK_TIMEOUT_SEC', 'DEEPSEEK_MAX_RETRIES',
        'USE_OLLAMA', 'OLLAMA_HOST', 'OLLAMA_MODEL',
        'LOG_LEVEL', 'LOG_FILE'
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


@app.post('/admin/llm-check')
def admin_llm_check():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    res = {
        'deepseek': {'enabled': False, 'configured': False, 'online': False, 'error': ''},
        'ollama': {'enabled': False, 'configured': False, 'online': False, 'error': ''},
    }
    # DeepSeek check
    try:
        use_ds = str(os.getenv('USE_DEEPSEEK', '')).strip() in ('1','true','yes','on')
        key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
        model = os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat'
        base = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').strip() or 'https://api.deepseek.com'
        # Normalize to include /v1 for compatibility
        base_norm = base.rstrip('/')
        if not base_norm.endswith('/v1'):
            base_norm = base_norm + '/v1'
        res['deepseek']['enabled'] = use_ds
        res['deepseek']['configured'] = bool(key)
        if use_ds and key:
            url = base_norm + '/chat/completions'
            payload = {
                'model': model,
                'messages': [{ 'role': 'user', 'content': 'ping' }],
                'max_tokens': 1,
                'stream': False,
            }
            status, j, err = _http_request_json('POST', url, headers={
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
            }, json_body=payload, timeout=5)
            if status and 200 <= status < 300:
                res['deepseek']['online'] = True
            elif err:
                res['deepseek']['error'] = err
    except Exception as exc:
        res['deepseek']['error'] = str(exc)

    # Ollama check
    try:
        use_ol = str(os.getenv('USE_OLLAMA', '')) in ('1','true','yes','on','')  # default allow
        host = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434').strip()
        model = os.getenv('OLLAMA_MODEL', '').strip()
        res['ollama']['enabled'] = use_ol
        res['ollama']['configured'] = bool(host)
        if use_ol and host:
            url = host.rstrip('/') + '/api/tags'
            status, _j, err = _http_request_json('GET', url, timeout=3)
            if status and 200 <= status < 300:
                res['ollama']['online'] = True
            elif err:
                res['ollama']['error'] = err
        # include model hint
        res['ollama']['model'] = model
    except Exception as exc:
        res['ollama']['error'] = str(exc)

    return jsonify(res)


@app.get('/admin/config/sms')
def admin_sms_config_echo():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    # Return whether SMS.ir/envs are set (without leaking secrets)
    return jsonify({
        'sms_ir_api_key_set': bool(os.getenv('SMS_IR_API_KEY','').strip()),
        'sms_ir_template_id': os.getenv('SMS_IR_TEMPLATE_ID',''),
        'sms_ir_verify_url': os.getenv('SMS_IR_VERIFY_URL','https://api.sms.ir/v1/send/verify'),
        'sms_ir_param_name': os.getenv('SMS_IR_PARAM_NAME','code'),
        'generic_api_url_set': bool(os.getenv('SMS_API_URL','').strip()),
        'generic_api_key_set': bool(os.getenv('SMS_API_KEY','').strip()),
        'generic_sender': os.getenv('SMS_SENDER','')
    })


@app.post('/draft')
def create_draft():
    _ensure_data_dirs()
    data = request.get_json(silent=True) or {}
    tpl_name = (data.get('template') or data.get('template_id') or '').strip() or 'sample_template.txt'
    fields: Dict[str, str] = data.get('fields') or {}
    tpl_path = os.path.join(DATA_DIR, 'templates', tpl_name)
    if not os.path.isfile(tpl_path):
        return jsonify({'error': 'template_not_found'}), 404
    try:
        with open(tpl_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as exc:
        return jsonify({'error': 'template_read_error', 'detail': str(exc)}), 500
    # simple placeholder replace: {key}
    out = str(content)
    if isinstance(fields, dict):
        for k, v in fields.items():
            out = out.replace('{'+str(k)+'}', str(v))
    return jsonify({'draft': out, 'template': tpl_name})


@app.post('/draft/save')
def save_draft():
    _ensure_data_dirs()
    data = request.get_json(silent=True) or {}
    draft = (data.get('draft') or '').strip()
    name = (data.get('name') or 'draft.txt').strip()
    if not draft:
        return jsonify({'error': 'empty_draft'}), 400
    # sanitize name
    name = re.sub(r"[^\w\u0600-\u06FF\.-]", "_", name)
    out_dir = os.path.join(DATA_DIR, 'output')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name if name.endswith('.txt') else (name + '.txt'))
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(draft)
    except Exception as exc:
        return jsonify({'error': 'write_failed', 'detail': str(exc)}), 500
    return jsonify({'ok': True, 'file': path})


@app.get('/draft/download')
def download_draft():
    _ensure_data_dirs()
    fname = (request.args.get('file') or '').strip()
    if not fname:
        return jsonify({'error': 'missing_file'}), 400
    # only allow from output dir
    out_dir = os.path.join(DATA_DIR, 'output')
    path = os.path.abspath(os.path.join(out_dir, fname))
    if not path.startswith(os.path.abspath(out_dir)):
        return jsonify({'error': 'forbidden'}), 403
    if not os.path.isfile(path):
        return jsonify({'error': 'not_found'}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            txt = f.read()
    except Exception as exc:
        return jsonify({'error': 'read_failed', 'detail': str(exc)}), 500
    resp = make_response(txt)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
    return resp


@app.get('/admin')
def admin_page():
    # Prefer new home template; fall back to old admin.html
    home_path = os.path.join(BASE_DIR, 'templates', 'admin', 'home.html')
    if os.path.exists(home_path):
        return render_template('admin/home.html')
    legacy = os.path.join(BASE_DIR, 'templates', 'admin', 'legacy.html')
    if os.path.exists(legacy):
        return render_template('admin/legacy.html')
    return make_response('<p>admin page not found</p>', 404)


@app.get('/admin/llm')
def admin_llm_page():
    llm_path = os.path.join(BASE_DIR, 'templates', 'admin', 'llm.html')
    if os.path.exists(llm_path):
        return render_template('admin/llm.html')
    return make_response('<p>admin llm page not found</p>', 404)


@app.get('/admin/data')
def admin_data_page():
    data_path = os.path.join(BASE_DIR, 'templates', 'admin', 'data.html')
    if os.path.exists(data_path):
        return render_template('admin/data.html')
    return make_response('<p>admin data page not found</p>', 404)


def _tail_file(path: str, max_lines: int = 200) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            if not lines:
                return ''
            return ''.join(lines[-max(1, int(max_lines)):])
    except Exception as exc:
        return f''


@app.get('/admin/logs')
def admin_logs_json():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
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


@app.get('/admin/logs/text')
def admin_logs_text():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    try:
        lines = int(request.args.get('lines', '200'))
    except Exception:
        lines = 200
    log_path = os.getenv('LOG_FILE', CURRENT_LOG_FILE or os.path.join(DATA_DIR, 'logs', 'app.log')).strip()
    content = _tail_file(log_path, max_lines=lines)
    resp = make_response(content or '')
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return resp


@app.get('/admin/logs/view')
def admin_logs_page():
    log_tpl = os.path.join(BASE_DIR, 'templates', 'admin', 'log.html')
    if os.path.exists(log_tpl):
        return render_template('admin/log.html')
    return make_response('<p>admin log page not found</p>', 404)


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """GitHub webhook endpoint for automatic deployment"""
    if request.method == 'POST':
        # اجرای اسکریپت آپدیت
        import subprocess
        subprocess.Popen(["bash", "/www/wwwroot/dadras/update-dadras.sh"])
        return jsonify({"status": "success", "message": "Deployment triggered ✅"}), 200
    else:
        return jsonify({"status": "waiting", "message": "Send a POST request from GitHub"}), 200


if __name__ == '__main__':
    _ensure_data_dirs()
    try:
        _apply_config_to_env(_read_config())
    except Exception:
        pass
    try:
        # Only index legal texts from data/texts for focused پاسخ از قوانین
        _ingest_directory(os.path.join(DATA_DIR, 'texts'), recursive=True)
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=False)


