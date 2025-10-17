import re
from bs4 import BeautifulSoup


def normalize_text(text: str) -> str:
    if not text:
        return ""
    s = text.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "").replace("\ufeff", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def tokenize_fa(text: str) -> list[str]:
    if not text:
        return []
    # very simple Persian/word tokenizer
    s = normalize_text(text)
    tokens = re.findall(r"[\w\u0600-\u06FF]+", s)
    return [t.lower() for t in tokens if t]


def split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"\n\s*\n+", text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 20]


def extract_text_from_html(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        # remove scripts/styles
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text(" ")
        return normalize_text(text)
    except Exception:
        return normalize_text(html)

import re

def normalize_text(s: str) -> str:
    if not s:
        return ''
    try:
        s = s.lower()
        s = re.sub(r"[\u200c\u200f\u200e\ufeff]", "", s)
        s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()
    except Exception:
        return s

def tokenize_fa(text: str):
    try:
        t = text or ''
        t = t.replace('\u200c', '').replace('\u200f', '').replace('\u200e', '').replace('\ufeff', '')
        t = t.lower()
        tokens = re.findall(r"[\u0600-\u06FF\w]+", t)
        return [tok for tok in tokens if tok and len(tok) > 1]
    except Exception:
        return (text or '').split()

def split_paragraphs(text: str, max_len: int = 600):
    parts = []
    for block in (text or '').split('\n\n'):
        b = block.strip()
        if not b:
            continue
        while len(b) > max_len:
            parts.append(b[:max_len])
            b = b[max_len:]
        if b:
            parts.append(b)
    return parts

def extract_text_from_html(html: str) -> str:
    if not html:
        return ''
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'noscript']):
            tag.extract()
        txt = soup.get_text(separator='\n')
        return '\n'.join([ln.strip() for ln in txt.splitlines() if ln.strip()])
    except Exception:
        try:
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        except Exception:
            return html


