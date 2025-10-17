from __future__ import annotations
import os
from typing import List, Dict, Any


class VectorLearner:
    """
    حداقل‌گرای بردار-یاب بدون وابستگی به FAISS.
    اگر SentenceTransformer موجود بود، از شباهت کیهانی استفاده می‌کنیم؛
    در غیر این صورت، امتیازدهی واژگانی ساده انجام می‌شود.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.index = None
        self.paragraphs: List[str] = []
        self.model_name: str | None = None
        self._embeddings = None

    def _maybe_load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model_name = os.getenv('EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
            return SentenceTransformer(self.model_name)
        except Exception:
            return None

    def build_from_texts(self, texts: List[str]) -> Dict[str, Any]:
        texts = [t for t in (texts or []) if t and len(t.strip()) >= 20]
        if not texts:
            return {"built": False, "reason": "no texts"}
        # ساده: پاراگراف‌سازی سطحی
        paragraphs: List[str] = []
        for t in texts:
            parts = [p.strip() for p in t.split('\n\n') if p and len(p.strip()) >= 20]
            paragraphs.extend(parts)
        if not paragraphs:
            return {"built": False, "reason": "no paragraphs"}

        model = self._maybe_load_model()
        if model is None:
            # حالت واژگانی: فقط لیست پاراگراف‌ها ذخیره می‌شود
            self.index = True
            self.paragraphs = paragraphs
            self._embeddings = None
            return {"built": True, "engine": "lexical"}

        # تع嵌ه‌ها را بساز
        import numpy as np  # type: ignore
        emb = model.encode(paragraphs, convert_to_numpy=True, normalize_embeddings=True)
        self.index = True  # نشانگر آماده‌بودن
        self.paragraphs = paragraphs
        self._embeddings = emb
        return {"built": True, "engine": "embeddings", "model": self.model_name}

    def load_if_exists(self) -> bool:
        # اجرای حداقلی: ایندکس دیسکی موجود نیست؛ همیشه False
        return False

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not (self.index and self.paragraphs):
            return []
        query = (query or '').strip()
        if not query:
            return []
        # اگر تع嵌ه‌ها موجود باشد، شباهت کیهانی؛ وگرنه واژگانی
        if self._embeddings is not None:
            try:
                from sentence_transformers import SentenceTransformer
                model = self._maybe_load_model()
                if model is None:
                    raise RuntimeError('no model')
                import numpy as np  # type: ignore
                q = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
                sims = (self._embeddings @ q).tolist()
                ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:max(1, top_k)]
                out: List[Dict[str, Any]] = []
                for i, sc in ranked:
                    out.append({"pid": int(i), "score": float(sc), "snippet": self.paragraphs[i]})
                return out
            except Exception:
                pass
        # واژگانی ساده
        import re
        q_terms = set(re.findall(r"[\w\u0600-\u06FF]+", query.lower()))
        scored = []
        for i, p in enumerate(self.paragraphs):
            p_terms = set(re.findall(r"[\w\u0600-\u06FF]+", p.lower()))
            score = len(q_terms & p_terms)
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        picked = scored[:max(1, top_k)]
        return [{"pid": int(i), "score": int(sc), "snippet": self.paragraphs[i]} for i, sc in picked]

import os
from typing import List, Dict

from services.vector_store import get_embedder
from utils.text import split_paragraphs


class VectorLearner:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.index = None
        self.paragraphs: List[str] = []
        self.model_name = None
        self.index_path = os.path.join(base_dir, 'vector_index', 'index.faiss')
        self.pars_path = os.path.join(base_dir, 'vector_index', 'paragraphs.txt')
        self.meta_path = os.path.join(base_dir, 'vector_index', 'meta.txt')

    def _faiss_available(self) -> bool:
        try:
            import faiss  # type: ignore
            _ = faiss
            return True
        except Exception:
            return False

    def load_if_exists(self) -> bool:
        if self.index is not None:
            return True
        if not (os.path.exists(self.index_path) and os.path.exists(self.pars_path)):
            return False
        try:
            import faiss  # type: ignore
            with open(self.pars_path, 'r', encoding='utf-8') as f:
                self.paragraphs = [ln.strip() for ln in f.readlines() if ln.strip()]
            self.index = faiss.read_index(self.index_path)
            if os.path.exists(self.meta_path):
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    self.model_name = f.read().strip()
            return True
        except Exception:
            return False

    def build_from_texts(self, texts: List[str]) -> Dict[str, object]:
        model, model_name = get_embedder()
        if model is None or not self._faiss_available():
            return {'built': False, 'reason': 'embedder_or_faiss_unavailable'}
        paras: List[str] = []
        for t in texts:
            paras.extend(split_paragraphs(t))
        uniq = []
        seen = set()
        for p in paras:
            k = (p or '').strip()
            if len(k) < 20:
                continue
            if k in seen:
                continue
            uniq.append(k)
            seen.add(k)
        if not uniq:
            return {'built': False, 'reason': 'no_paragraphs'}
        import numpy as np  # type: ignore
        import faiss  # type: ignore
        emb = model.encode(uniq, convert_to_numpy=True, normalize_embeddings=True)
        dim = emb.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(emb)
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(index, self.index_path)
        with open(self.pars_path, 'w', encoding='utf-8') as f:
            for p in uniq:
                f.write(p.replace('\n', ' ') + '\n')
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            f.write(model_name or '')
        self.index = index
        self.paragraphs = uniq
        self.model_name = model_name
        return {'built': True, 'count': len(uniq), 'model': model_name}

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, object]]:
        if not query:
            return []
        if self.index is None and not self.load_if_exists():
            return []
        model, _ = get_embedder()
        if model is None:
            return []
        import numpy as np  # type: ignore
        D, I = self.index.search(model.encode([query], convert_to_numpy=True, normalize_embeddings=True), top_k)
        out = []
        for idx, score in zip(I[0], D[0]):
            if idx < 0 or idx >= len(self.paragraphs):
                continue
            out.append({'pid': int(idx), 'score': float(score), 'snippet': self.paragraphs[idx]})
        return out


