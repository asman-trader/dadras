import os


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        raise RuntimeError("کتابخانه PyMuPDF (بسته pymupdf) نصب نیست. دستور نصب: pip install pymupdf") from exc
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text.strip()


def extract_text_with_pdfminer(pdf_path: str) -> str:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
    except Exception:
        return ""
    try:
        mined = pdfminer_extract_text(pdf_path)
        return (mined or "").strip()
    except Exception:
        return ""


def extract_text_via_ocr(pdf_path: str) -> str:
    try:
        import fitz
        from PIL import Image  # pillow
        import pytesseract
    except Exception as exc:
        raise RuntimeError("برای OCR نیاز به نصب pillow و pytesseract و Tesseract OCR دارید.") from exc

    if os.name == 'nt':
        user_path = os.getenv('TESSERACT_PATH')
        candidates = []
        if user_path:
            candidates.append(user_path)
        candidates.extend([
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
        ])
        for p in candidates:
            if os.path.exists(p):
                try:
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
                except Exception:
                    pass

    doc = fitz.open(pdf_path)
    ocr_text_parts = []
    upscale_matrix = fitz.Matrix(3, 3)
    for page in doc:
        pix = page.get_pixmap(matrix=upscale_matrix)
        mode = "RGB" if pix.alpha == 0 else "RGBA"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        try:
            text_page = pytesseract.image_to_string(img, lang="fas+eng")
        except Exception:
            text_page = pytesseract.image_to_string(img, lang="eng")
        if text_page:
            ocr_text_parts.append(text_page)
    return "\n".join(ocr_text_parts).strip()


def _str_to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on', 'y')


def extract_text(pdf_path: str) -> str:
    base_text = extract_text_from_pdf(pdf_path)
    if base_text and len(base_text.strip()) >= 5:
        return base_text.strip()
    miner_text = extract_text_with_pdfminer(pdf_path)
    if miner_text and len(miner_text.strip()) >= 5:
        return miner_text.strip()
    if _str_to_bool(os.getenv('OCR', '1'), default=True):
        try:
            return extract_text_via_ocr(pdf_path)
        except Exception:
            return (base_text or "").strip()
    return (base_text or "").strip()


def extract_text_fast(pdf_path: str) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
        if text and len(text.strip()) >= 3:
            return text.strip()
    except Exception:
        pass
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        mined = pdfminer_extract_text(pdf_path)
        return (mined or "").strip()
    except Exception:
        return ""


