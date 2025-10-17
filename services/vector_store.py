import os

EMBEDDER = { 'model': None, 'name': None }

def get_embedder():
    if EMBEDDER.get('model') is not None:
        return EMBEDDER['model'], EMBEDDER.get('name')
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv('EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
        model = SentenceTransformer(model_name)
        EMBEDDER['model'] = model
        EMBEDDER['name'] = model_name
        return model, model_name
    except Exception:
        return None, None


