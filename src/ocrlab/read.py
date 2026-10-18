"""Reading a page: its text layer when it has one, else the page rendered and read by Tesseract. A page comes back as
words and lines, each with its box on the page in PDF points (72 a inch, from the top left) and, for OCR, Tesseract's
confidence (0 to 100). Results are cached by the file's path, size and time, the page and the settings."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .config import out, tesseract

TEXT_MIN_CHARS = 20          # a page with fewer letters than this in its text layer has none worth using


def _doc(path):
    import pymupdf
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("no file %s" % p)
    return pymupdf.open(str(p))


def _key(path, *parts):
    p = Path(path).resolve()
    st = p.stat()
    h = hashlib.sha1(("%s|%d|%d" % (p, st.st_size, int(st.st_mtime))).encode()).hexdigest()[:16]
    return out("cache", h), "_".join(str(x) for x in parts)


def pages_of(spec, n):
    """A page list from '3', '1-5', '1,4,9-12' or None (all); pages count from 1."""
    if spec in (None, "", "all"):
        return list(range(1, n + 1))
    got = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            got += list(range(int(a), int(b) + 1))
        elif part:
            got.append(int(part))
    bad = [p for p in got if p < 1 or p > n]
    if bad:
        raise ValueError("pages %s outside 1 to %d" % (bad, n))
    return got


def info(path):
    """How many pages, and which have a usable text layer (the rest need OCR)."""
    d = _doc(path)
    has = []
    for i, pg in enumerate(d):
        if len(re.sub(r"\s", "", pg.get_text("text"))) >= TEXT_MIN_CHARS:
            has.append(i + 1)
    n = len(d)
    return {"file": str(path), "pages": n, "text_layer_pages": len(has), "needs_ocr": [p for p in range(1, n + 1) if p not in has],
            "tesseract": tesseract()}


def parse_tsv(tsv, scale=1.0):
    """Tesseract's TSV as words and lines. scale turns its pixels into the page's units (72 / dpi for PDF points)."""
    words, lines = [], {}
    rows = tsv.splitlines()
    for row in rows[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        text = c[11].strip()
        if not text:
            continue
        x, y, w, h = (float(v) * scale for v in c[6:10])
        conf = float(c[10])
        wd = {"text": text, "conf": round(conf, 1), "box": [round(x, 2), round(y, 2), round(x + w, 2), round(y + h, 2)]}
        words.append(wd)
        lines.setdefault((int(c[2]), int(c[3]), int(c[4])), []).append(wd)
    out_lines = []
    for k in sorted(lines):
        ws = lines[k]
        out_lines.append({"text": " ".join(w["text"] for w in ws),
                          "box": [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
                                  max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)],
                          "conf": round(sum(w["conf"] for w in ws) / len(ws), 1)})
    out_lines.sort(key=lambda l_: (round(l_["box"][1] / 4.0), l_["box"][0]))
    return words, out_lines


def ocr_image(image, lang="eng", psm=3, scale=1.0):
    """An image file read by Tesseract: (words, lines). psm: Tesseract's page layout mode (3 a page, 4 a column, 6 a
    block, 11 sparse text)."""
    exe = tesseract()
    if not exe:
        raise FileNotFoundError("Tesseract is not installed (set OCRLAB_TESSERACT to tesseract's path)")
    p = subprocess.run([exe, str(image), "stdout", "-l", lang, "--psm", str(int(psm)), "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if p.returncode != 0:
        raise ValueError("tesseract failed: %s" % (p.stderr or "").strip()[-400:])
    return parse_tsv(p.stdout, scale)


def _text_layer(pg):
    words, lines = [], {}
    for x0, y0, x1, y1, t, b, ln, _wn in pg.get_text("words"):
        wd = {"text": t, "conf": None, "box": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]}
        words.append(wd)
        lines.setdefault((b, ln), []).append(wd)
    out_lines = []
    for k in sorted(lines):
        ws = lines[k]
        out_lines.append({"text": " ".join(w["text"] for w in ws),
                          "box": [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
                                  max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)], "conf": None})
    out_lines.sort(key=lambda l_: (round(l_["box"][1] / 4.0), l_["box"][0]))
    return words, out_lines


def page(path, n, dpi=300, lang="eng", psm=3, force_ocr=False):
    """Page n (from 1): {page, source (text_layer | ocr), text, lines, words, mean_conf, size_pt}. The text layer is
    used when the page has one, unless force_ocr (a scan's hidden layer can be poor)."""
    d = _doc(path)
    if not 1 <= n <= len(d):
        raise ValueError("page %d outside 1 to %d" % (n, len(d)))
    pg = d[n - 1]
    has = len(re.sub(r"\s", "", pg.get_text("text"))) >= TEXT_MIN_CHARS
    src = "text_layer" if has and not force_ocr else "ocr"
    folder, name = _key(path, "p%d" % n, src, dpi if src == "ocr" else 0, lang, psm)
    cached = folder / (name + ".json")
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    if src == "text_layer":
        words, lines = _text_layer(pg)
    else:
        pix = pg.get_pixmap(dpi=int(dpi))
        fd, png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            pix.save(png)
            words, lines = ocr_image(png, lang=lang, psm=psm, scale=72.0 / float(dpi))
        finally:
            os.remove(png)
    confs = [w["conf"] for w in words if w["conf"] is not None and w["conf"] >= 0]
    res = {"file": str(path), "page": n, "source": src, "dpi": dpi if src == "ocr" else None, "lang": lang, "psm": psm,
           "size_pt": [round(pg.rect.width, 1), round(pg.rect.height, 1)],
           "text": "\n".join(l_["text"] for l_ in lines), "lines": lines, "words": words,
           "mean_conf": round(sum(confs) / len(confs), 1) if confs else None}
    cached.write_text(json.dumps(res), encoding="utf-8")
    return res


def find(path, pattern, pages=None, regex=True, dpi=300, lang="eng", force_ocr=False, context=1, limit=50):
    """Every line matching pattern (a regular expression, case ignored; or plain text), with its page, box,
    confidence and the lines round it."""
    d = _doc(path)
    rx = re.compile(pattern if regex else re.escape(pattern), re.I)
    hits = []
    for n in pages_of(pages, len(d)):
        pr = page(path, n, dpi=dpi, lang=lang, force_ocr=force_ocr)
        ls = pr["lines"]
        for i, l_ in enumerate(ls):
            if rx.search(l_["text"]):
                hits.append({"page": n, "source": pr["source"], "line": l_["text"], "box": l_["box"], "conf": l_["conf"],
                             "before": [x["text"] for x in ls[max(0, i - context):i]],
                             "after": [x["text"] for x in ls[i + 1:i + 1 + context]]})
                if len(hits) >= limit:
                    return hits
    return hits


def words_in(path, n, box, dpi=300, lang="eng", force_ocr=False):
    """The words whose middle lies inside box ([x0, y0, x1, y1] in PDF points), top to bottom, left to right: a
    table's column read on its own."""
    pr = page(path, n, dpi=dpi, lang=lang, force_ocr=force_ocr)
    x0, y0, x1, y1 = box
    got = [w for w in pr["words"] if x0 <= (w["box"][0] + w["box"][2]) / 2 <= x1 and y0 <= (w["box"][1] + w["box"][3]) / 2 <= y1]
    got.sort(key=lambda w: (round(w["box"][1] / 4.0), w["box"][0]))
    return got
