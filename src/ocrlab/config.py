"""Where OCR Lab writes (OCRLAB_OUT, ~/.ocrlab: its page cache) and where Tesseract is (OCRLAB_TESSERACT, else on the
PATH, else the usual install folders)."""
import os
import shutil
from pathlib import Path


def out(*parts):
    p = Path(os.environ.get("OCRLAB_OUT") or Path.home() / ".ocrlab").joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def tesseract():
    """The Tesseract program's path, or None when it is not installed."""
    env = os.environ.get("OCRLAB_TESSERACT")
    if env and Path(env).exists():
        return env
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"):
        if Path(c).exists():
            return c
    return None
