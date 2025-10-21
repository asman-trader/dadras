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
TEXTS_DIR = os.path.join(DATA_DIR, 'laws')


def _ensure_data_dirs() -> None:
    for sub in ('laws', 'cases', 'templates', 'output', 'logs', 'texts'):
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
    return response


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
    }


def _normalize_text(s: str) -> str:
    if not s:
        return ''
    s = s.lower()
    # remove zero-width chars and punctuation-like
    s = re.sub(r"[\u200c\u200f\u200e\ufeff]", "", s)
    return s


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
    cid = request.cookies.get('client_id')
    if cid and isinstance(cid, str) and len(cid) >= 8:
        return cid
    return uuid.uuid4().hex


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
    # very light keyword rules
    domains = {
        'family': ['نفقه', 'طلاق', 'حضانت', 'مهریه'],
        'criminal': ['کیفری', 'سرقت', 'کلاهبرداری', 'ضرب و جرح'],
        'commerce': ['قرارداد', 'شرکت', 'تجارت', 'چک', 'اسناد تجاری'],
        'property': ['تصرف', 'ملک', 'پلاک', 'رفع تصرف', 'عدوانی'],
    }
    intents = {
        'advice': ['مشاوره', 'راهکار', 'چه کنم', 'قانون'],
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


def _deepseek_chat(question: str, context: str) -> Tuple[bool, str]:
    """Call DeepSeek via OpenAI SDK with retries; returns (ok, text_or_error)."""
    key = (os.getenv('DEEPSEEK_API_KEY', '').strip() or DEFAULT_DEEPSEEK_API_KEY)
    if not key:
        return False, 'DEEPSEEK_API_KEY not set'
    model = (os.getenv('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat')
    system = 'شما یک دستیار حقوقی فارسی هستید. پاسخ کوتاه، دقیق و مستند بده.'
    user = f"[زمینه]\n{context}\n\n[سؤال]\n{question}"
    try:
        client = _get_openai_client()
    except Exception as exc:
        return False, f'OpenAI client error: {exc}'

    last_error = ''
    for attempt in range(max(1, DEEPSEEK_MAX_RETRIES)):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=False,
                max_tokens=512,
                timeout=DEEPSEEK_TIMEOUT_SEC,
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
    dir_path = data.get('dir') or os.path.join(DATA_DIR, 'laws')
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


# Notes routes moved to routes/notes.py blueprint

@app.post('/ingest')
def ingest_endpoint():
    guard = _require_admin_if_configured()
    if guard is not None:
        return guard
    _ensure_data_dirs()
    data = request.get_json(silent=True) or {}
    dir_path = data.get('dir') or DATA_DIR
    recursive = bool(data.get('recursive', True))
    files_loaded, paragraphs_added = _ingest_directory(dir_path, recursive=recursive)
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


@app.post('/ask')
def ask_endpoint():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    try:
        top_k = int(data.get('top_k', 5))
    except Exception:
        top_k = 5
    meta = _detect_intent_domain(question)
    cid = _get_client_id()
    # rate limit per client/ip
    rl_key = request.remote_addr or cid
    ok, remaining = _check_rate_limit(rl_key, RATE_LIMIT_ASK, RATE_WINDOW_SEC)
    if not ok:
        return jsonify({'error': 'rate_limited', 'retry_in_sec': RATE_WINDOW_SEC, 'limit': RATE_LIMIT_ASK}), 429
    _append_session(cid, 'user', question)
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
        ok, ds_text = _deepseek_chat(question, rag_context)
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


if __name__ == '__main__':
    _ensure_data_dirs()
    try:
        _apply_config_to_env(_read_config())
    except Exception:
        pass
    try:
        _ingest_directory(DATA_DIR, recursive=True)
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)


