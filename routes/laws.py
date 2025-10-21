import os
import re
import time
from typing import Dict, Any, List, Tuple
from flask import Blueprint, request, jsonify, render_template


laws_bp = Blueprint('laws', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(APP_DIR, 'data')
LAWS_DIR = os.path.join(DATA_DIR, 'laws')
from flask import current_app as app


LAW_CACHE: Dict[str, Dict[str, Any]] = {}
LAW_CACHE_MTIME: Dict[str, float] = {}


def _normalize_text(s: str) -> str:
    if not s:
        return ''
    s = s.lower()
    s = re.sub(r"[\u200c\u200f\u200e\ufeff]", "", s)
    return s


def _tokenize(text: str) -> List[str]:
    text = _normalize_text(text)
    return re.findall(r"[\w\d\u0600-\u06FF]+", text)


def _iter_law_files() -> List[str]:
    if not os.path.isdir(LAWS_DIR):
        return []
    items: List[str] = []
    for name in os.listdir(LAWS_DIR):
        if name.lower().endswith('.txt'):
            items.append(os.path.join(LAWS_DIR, name))
    return items


def _parse_articles(text: str) -> Dict[str, str]:
    # Split by Persian article headers like: "ماده 1 -" ... until next "ماده <num>"
    articles: Dict[str, str] = {}
    if not text:
        return articles
    # Normalize line endings
    t = text.replace('\r\n', '\n')
    # Find article starts
    pattern = re.compile(r"(?m)^\s*ماده\s+(\d+)\s*[-–:]*\s*")
    matches = list(pattern.finditer(t))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(t)
        num = m.group(1)
        body = t[start:end].strip()
        if body:
            articles[num] = body
    return articles


def _ensure_loaded() -> None:
    for fp in _iter_law_files():
        try:
            mtime = os.path.getmtime(fp)
        except Exception:
            continue
        if LAW_CACHE.get(fp) and LAW_CACHE_MTIME.get(fp) == mtime:
            continue
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        articles = _parse_articles(content)
        LAW_CACHE[fp] = {
            'file': os.path.basename(fp),
            'path': fp,
            'text': content,
            'articles': articles,
            'size': len(content or ''),
        }
        LAW_CACHE_MTIME[fp] = mtime


def _search_in_text(text: str, query: str, max_hits: int = 5) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    if not text or not (query or '').strip():
        return hits
    qn = _normalize_text(query)
    tn = _normalize_text(text)
    # naive substring search, collect windows
    for m in re.finditer(re.escape(qn), tn):
        i = m.start()
        a = max(0, i - 120)
        b = min(len(tn), i + 180)
        snippet = text[a:b].replace('\n', ' ')
        hits.append((i, snippet))
        if len(hits) >= max_hits:
            break
    return hits


@laws_bp.get('/laws')
def laws_page():
    _ensure_loaded()
    return render_template('laws/index.html')


@laws_bp.get('/laws/list')
def laws_list():
    _ensure_loaded()
    items = []
    for fp, meta in LAW_CACHE.items():
        try:
            st = os.stat(fp)
        except Exception:
            continue
        items.append({
            'file': meta.get('file') or os.path.basename(fp),
            'size': int(st.st_size),
            'mtime': int(st.st_mtime),
            'articles': len(meta.get('articles') or {}),
        })
    items.sort(key=lambda x: x['file'])
    return jsonify({'ok': True, 'items': items})


@laws_bp.get('/laws/article')
def laws_article():
    _ensure_loaded()
    file_name = (request.args.get('file') or '').strip()
    num = (request.args.get('num') or '').strip()
    if not file_name or not num:
        return jsonify({'ok': False, 'error': 'missing_params'}), 400
    target = None
    for fp, meta in LAW_CACHE.items():
        if os.path.basename(fp) == file_name:
            target = meta
            break
    if not target:
        return jsonify({'ok': False, 'error': 'file_not_found'}), 404
    art = (target.get('articles') or {}).get(num)
    if not art:
        return jsonify({'ok': False, 'error': 'article_not_found'}), 404
    return jsonify({'ok': True, 'file': file_name, 'num': num, 'text': art})


@laws_bp.get('/laws/search')
def laws_search():
    _ensure_loaded()
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'ok': True, 'items': []})
    # Direct article query like: "ماده 123"
    m = re.search(r"ماده\s+(\d+)", q)
    if m:
        num = m.group(1)
        items = []
        for fp, meta in LAW_CACHE.items():
            if num in (meta.get('articles') or {}):
                items.append({'type': 'article', 'file': meta.get('file'), 'num': num, 'snippet': (meta['articles'][num] or '')[:220]})
        return jsonify({'ok': True, 'items': items})
    # Otherwise do naive search across texts
    out = []
    for fp, meta in LAW_CACHE.items():
        text = meta.get('text') or ''
        hits = _search_in_text(text, q, max_hits=3)
        for pos, snip in hits:
            out.append({'type': 'snippet', 'file': meta.get('file'), 'pos': pos, 'snippet': snip})
    # rank by earliest position (rough relevance)
    out.sort(key=lambda x: x.get('pos', 0))
    return jsonify({'ok': True, 'items': out[:20]})


def _clean_text_blocks(text: str) -> str:
    # Basic normalization: unify line endings, trim, collapse multiple blank lines, remove zero-width chars
    t = (text or '').replace('\r\n', '\n')
    t = re.sub(r"[\u200c\u200f\u200e\ufeff]", "", t)
    # Normalize spaces around punctuation-like dashes
    t = re.sub(r"\s+–\s+", " – ", t)
    # Collapse 3+ newlines to 2
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + '\n'


@laws_bp.post('/admin/laws/normalize')
def laws_normalize():
    # Admin guard using the app's helper if available
    try:
        from flask import g
        ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '').strip()
        provided = request.headers.get('X-Admin-Token') or request.headers.get('X-Token')
        if ADMIN_TOKEN and (not provided or provided.strip() != ADMIN_TOKEN):
            return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    except Exception:
        pass
    data = request.get_json(silent=True) or {}
    file_name = (data.get('file') or 'قانون-مدنی.txt').strip()
    src = os.path.join(LAWS_DIR, file_name)
    if not os.path.isfile(src):
        return jsonify({'ok': False, 'error': 'file_not_found'}), 404
    try:
        with open(src, 'r', encoding='utf-8') as f:
            raw = f.read()
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'read_failed', 'detail': str(exc)}), 500
    cleaned = _clean_text_blocks(raw)
    arts = _parse_articles(cleaned)
    # Write normalized copy next to it
    out_path = os.path.join(LAWS_DIR, os.path.splitext(file_name)[0] + '.normalized.txt')
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            # write header and then ordered articles
            f.write(f"# Normalized copy of {file_name}\n\n")
            for k in sorted(arts, key=lambda x:int(x)):
                f.write(f"ماده {k} - \n")
                f.write(arts[k].strip()+"\n\n")
    except Exception as exc:
        return jsonify({'ok': False, 'error': 'write_failed', 'detail': str(exc)}), 500
    # refresh cache
    try:
        LAW_CACHE.pop(src, None); LAW_CACHE_MTIME.pop(src, None)
    except Exception:
        pass
    return jsonify({'ok': True, 'normalized_file': os.path.basename(out_path), 'articles': len(arts)})


