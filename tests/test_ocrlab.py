"""OCR Lab: the TSV parser, the page list, the text layer, and a real OCR read of a page with no text layer (skipped
when Tesseract is not installed)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocrlab import read as R  # noqa: E402
from ocrlab.config import tesseract  # noqa: E402

TSV = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
       "1\t1\t0\t0\t0\t0\t0\t0\t600\t800\t-1\t\n"
       "5\t1\t1\t1\t1\t1\t100\t50\t60\t20\t96.5\tLength\n"
       "5\t1\t1\t1\t1\t2\t170\t50\t30\t20\t91.0\tof\n"
       "5\t1\t1\t1\t2\t1\t100\t90\t40\t20\t88.0\t8.593\n")


def test_parse_tsv_words_lines_scale():
    words, lines = R.parse_tsv(TSV, scale=0.5)
    assert [w["text"] for w in words] == ["Length", "of", "8.593"]
    assert words[0]["box"] == [50.0, 25.0, 80.0, 35.0]
    assert [l_["text"] for l_ in lines] == ["Length of", "8.593"]
    assert lines[0]["conf"] == pytest.approx(93.8, abs=0.1)


def test_pages_of():
    assert R.pages_of(None, 3) == [1, 2, 3]
    assert R.pages_of("1,3-4", 5) == [1, 3, 4]
    with pytest.raises(ValueError):
        R.pages_of("7", 5)


@pytest.fixture()
def pdfs(tmp_path, monkeypatch):
    import pymupdf
    monkeypatch.setenv("OCRLAB_OUT", str(tmp_path / "out"))
    text = tmp_path / "text.pdf"
    d = pymupdf.open()
    pg = d.new_page()
    pg.insert_text((72, 100), "Overall length 8.593 inches", fontsize=14)
    pg.insert_text((72, 130), "Weight 2.437 pounds", fontsize=14)
    d.save(str(text))
    # the same page as a picture only: a scan with no text layer
    pix = d[0].get_pixmap(dpi=300)
    png = tmp_path / "scan.png"
    pix.save(str(png))
    scan = tmp_path / "scan.pdf"
    s = pymupdf.open()
    sp = s.new_page(width=d[0].rect.width, height=d[0].rect.height)
    sp.insert_image(sp.rect, filename=str(png))
    s.save(str(scan))
    return text, scan


def test_text_layer(pdfs):
    text, scan = pdfs
    i = R.info(str(text))
    assert i["pages"] == 1 and i["needs_ocr"] == []
    assert R.info(str(scan))["needs_ocr"] == [1]
    p = R.page(str(text), 1)
    assert p["source"] == "text_layer"
    assert "8.593" in p["text"]
    h = R.find(str(text), r"overall\s+length")
    assert len(h) == 1 and h[0]["page"] == 1 and h[0]["box"][1] < 100


@pytest.mark.skipif(not tesseract(), reason="Tesseract is not installed")
def test_ocr_reads_a_scan(pdfs):
    _text, scan = pdfs
    p = R.page(str(scan), 1, dpi=300)
    assert p["source"] == "ocr"
    assert "8.593" in p["text"] and "Weight" in p["text"]
    assert p["mean_conf"] > 70
    h = R.find(str(scan), r"weight")
    assert h and 115 < h[0]["box"][3] < 145          # the line's box lands where it was printed (y 130 pt)
    w = R.words_in(str(scan), 1, [60, 85, 400, 105])
    assert "8.593" in [x["text"] for x in w] and "Weight" not in [x["text"] for x in w]
    again = R.page(str(scan), 1, dpi=300)            # from the cache
    assert again["text"] == p["text"]


def test_lines_follow_lands_on_a_drawn_box(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from ocrlab import lines as L
    img = np.full((200, 300), 255, np.uint8)
    cv2.rectangle(img, (60, 50), (240, 150), 0, 3)                 # the part's line
    cv2.line(img, (60, 70), (240, 70), 0, 3)                         # an inner line 20 px below its top
    rough = [[52, 58], [248, 44], [246, 158], [55, 141]]             # a crude reading, up to 8 px off
    r = L.follow(img, rough, picture=str(tmp_path / "f.png"))
    assert r["fit_before"]["p95_px"] > 4
    assert r["fit_after"]["p95_px"] <= 1.5
    ys = [p[1] for p in L.dense(r["outline_px"], 1.0) if 80 < p[0] < 220]
    assert min(ys) < 53 and max(ys) > 147                           # on the box, not on the inner line
    assert (tmp_path / "f.png").exists()


def test_lines_fit_counts_a_miss():
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from ocrlab import lines as L
    img = np.full((100, 100), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (80, 80), 0, 1)
    assert L.fit(img, [[20, 20], [80, 20], [80, 80], [20, 80]])["p95_px"] <= 1.0
    assert L.fit(img, [[25, 25], [75, 25], [75, 75], [25, 75]])["mean_px"] >= 4.0


def test_untangle_cuts_a_loop():
    from ocrlab import lines as L
    bow = [[0, 0], [10, 0], [10, 10], [12, 12], [14, 10], [12, 8], [10, 10.5], [0, 10]]   # a small loop near a corner
    assert L.crossings(bow) >= 1
    out, cut = L.untangle(bow)
    assert cut >= 1 and L.crossings(out) == 0
    assert abs(L._area(out)) > 90                      # the box stays, the loop goes
