"""Turn a file (PDF, image, text) into plain text, with OCR word confidences for scanned pages."""

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz
from PIL import Image

MIN_PAGE_CHARS = 50  # a PDF page with less text than this is treated as scanned
OCR_DPI = 300
DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class Document:
    text: str
    source_type: str  # text | pdf_digital | pdf_scanned | pdf_mixed | image
    pages: int = 1
    ocr_words: dict[str, float] = field(default_factory=dict)  # lowercased word -> confidence 0..1
    ocr_text: str = ""  # the part of `text` that came from OCR

    def __post_init__(self):
        # NFKC folds ligatures ("ﬁ" -> "fi") and odd spaces so values can be matched against the text
        self.text = unicodedata.normalize("NFKC", self.text)
        self.ocr_text = unicodedata.normalize("NFKC", self.ocr_text)


def from_text(text: str) -> Document:
    return Document(text=text, source_type="text")


def load(path: str | Path) -> Document:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".eml"):
        return from_text(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        text, words = _ocr(Image.open(path))
        return Document(text=text, source_type="image", ocr_words=words, ocr_text=text)
    raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path) -> Document:
    texts, ocr_texts, words, scanned = [], [], {}, 0
    with fitz.open(path) as pdf:
        for page in pdf:
            text = _layout_text(page)
            if len(text.strip()) < MIN_PAGE_CHARS or _garbled(text):
                pix = page.get_pixmap(dpi=OCR_DPI, colorspace=fitz.csGRAY)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                text, page_words = _ocr(img)
                for w, c in page_words.items():
                    words[w] = max(c, words.get(w, 0.0))
                ocr_texts.append(text)
                scanned += 1
            texts.append(text)
        n = len(pdf)
    kind = "pdf_digital" if scanned == 0 else "pdf_scanned" if scanned == n else "pdf_mixed"
    return Document(text="\n\n".join(texts), source_type=kind, pages=n, ocr_words=words,
                    ocr_text="\n\n".join(ocr_texts))


def _layout_text(page, tol: float = 4.0) -> str:
    """Rebuild lines from word positions so table rows stay on one line (also handles rotated pages)."""
    m = page.rotation_matrix
    words = sorted(((fitz.Rect(w[:4]) * m, w[4]) for w in page.get_text("words")), key=lambda rw: rw[0].y1)
    rows: list[list] = []
    for rect, w in words:
        if rows and abs(rect.y1 - rows[-1][0]) <= tol:
            rows[-1][1].append((rect.x0, w))
        else:
            rows.append([rect.y1, [(rect.x0, w)]])
    return "\n".join(" ".join(w for _, w in sorted(ws)) for _, ws in rows)


def _garbled(text: str) -> bool:
    """A text layer with lots of very long 'words' has lost its spaces ('CityofRamseyPublicWorks'); OCR it instead."""
    tokens = text.split()
    return bool(tokens) and sum(len(t) >= 20 for t in tokens) / len(tokens) > 0.05


def _ocr(img: Image.Image) -> tuple[str, dict[str, float]]:
    """OCR an image. Returns text (rebuilt line by line) and {word: confidence 0..1}."""
    import pytesseract

    cmd = os.getenv("TESSERACT_CMD") or (DEFAULT_TESSERACT if Path(DEFAULT_TESSERACT).exists() else None)
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract is required for scanned documents. Install it "
            "(Windows: `winget install UB-Mannheim.TesseractOCR`) or set TESSERACT_CMD."
        ) from e

    lines: dict[tuple, list[str]] = {}
    words: dict[str, float] = {}
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if not word.strip() or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        w = _clean_word(word)
        if w:
            words[w] = max(conf / 100, words.get(w, 0.0))
    return "\n".join(" ".join(ws) for ws in lines.values()), words


def _clean_word(word: str) -> str:
    return re.sub(r"[^\w.$/-]", "", word.lower()).strip(".")
