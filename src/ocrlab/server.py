"""OCR Lab over MCP. Run: ocrlab-mcp (or python -m ocrlab serve)."""
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from . import __version__, lines as L, read as R

mcp = MCPServer("ocrlab", title="OCR Lab", version=__version__, instructions=(
    "OCR Lab reads the text of scanned documents. A PDF page with a text layer is read from it; a page without one "
    "is rendered and read by Tesseract. Every line and word comes with its box on the page (PDF points from the top "
    "left) and, when read by OCR, a confidence from 0 to 100. Start with pdf_info, then find a label (find) or read "
    "a page (read_page); read a table's column alone with words_in. OCR misreads: check a number on the page picture "
    "before you rely on it. For drawings: line_fit says how far an outline sits off the picture's lines, line_follow "
    "lays a rough outline onto them as one line."))


def _err(f, *a, **k):
    try:
        return f(*a, **k)
    except (ValueError, FileNotFoundError) as e:
        raise ToolError(str(e))


@mcp.tool()
def pdf_info(path: str) -> dict:
    """A PDF's page count, which pages have a text layer and which need OCR, and where Tesseract is."""
    return _err(R.info, path)


@mcp.tool()
def read_page(path: str, page: Annotated[int, Field(description="from 1")],
              dpi: Annotated[int, Field(description="render resolution for OCR")] = 300,
              psm: Annotated[int, Field(description="Tesseract layout: 3 a page, 4 a column, 6 a block, 11 sparse")] = 3,
              lang: str = "eng", force_ocr: bool = False, words: bool = False) -> dict:
    """One page's text and lines (boxes in PDF points, OCR confidence); with words, every word too."""
    r = _err(R.page, path, page, dpi=dpi, lang=lang, psm=psm, force_ocr=force_ocr)
    return r if words else {k: v for k, v in r.items() if k != "words"}


@mcp.tool()
def read_pages(path: str, pages: Annotated[str, Field(description="'3', '1-5', '1,4,9-12' or 'all'")],
               dpi: int = 300, lang: str = "eng", force_ocr: bool = False) -> dict:
    """Several pages read and cached; each page's source, line count and mean confidence (read_page gives the text)."""
    d = _err(R.info, path)
    res = []
    for n in _err(R.pages_of, pages, d["pages"]):
        r = _err(R.page, path, n, dpi=dpi, lang=lang, force_ocr=force_ocr)
        res.append({"page": n, "source": r["source"], "lines": len(r["lines"]), "mean_conf": r["mean_conf"]})
    return {"file": path, "pages": res}


@mcp.tool()
def find(path: str, pattern: Annotated[str, Field(description="a regular expression, case ignored")],
         pages: str | None = None, regex: bool = True, dpi: int = 300, force_ocr: bool = False,
         context: int = 1, limit: int = 50) -> dict:
    """Every line matching the pattern, with its page, box, confidence and the lines round it."""
    return {"hits": _err(R.find, path, pattern, pages=pages, regex=regex, dpi=dpi, force_ocr=force_ocr, context=context, limit=limit)}


@mcp.tool()
def words_in(path: str, page: int, box: Annotated[list[float], Field(description="[x0, y0, x1, y1] in PDF points from the top left")],
             dpi: int = 300, force_ocr: bool = False) -> dict:
    """The words inside a box on a page, in reading order: one column of a table read on its own."""
    if len(box) != 4:
        raise ToolError("box must be [x0, y0, x1, y1]")
    return {"words": _err(R.words_in, path, page, box, dpi=dpi, force_ocr=force_ocr)}


@mcp.tool()
def read_image(path: str, psm: int = 3, lang: str = "eng") -> dict:
    """An image file read by Tesseract: its lines (boxes in pixels) and their confidence."""
    words, lines = _err(R.ocr_image, path, lang=lang, psm=psm)
    return {"text": "\n".join(l_["text"] for l_ in lines), "lines": lines, "words": len(words)}


@mcp.tool()
def line_fit(path: str, outline: Annotated[list[list[float]], Field(description="a closed outline, [[x, y], ...] in px")],
             mode: Annotated[str, Field(description="auto, lines (line art) or photo")] = "auto") -> dict:
    """How far a closed outline sits off the picture's lines: each point's distance to the nearest line's middle,
    every 1 px along it (mean, 95th percentile, largest, share within 1.5 px)."""
    return _err(L.fit, path, outline, mode=mode)


@mcp.tool()
def line_follow(path: str, outline: Annotated[list[list[float]], Field(description="a rough closed outline, [[x, y], ...] in px")],
                radius_px: Annotated[float, Field(description="how far a point may move along its normal")] = 16,
                smooth: Annotated[float, Field(description="the price of 1 px of difference between neighbours")] = 0.6,
                mode: str = "auto", picture: Annotated[str | None, Field(description="a path for the picture")] = None) -> dict:
    """A rough outline laid onto the picture's lines as one line: each point moves only along its normal, all moves
    chosen together, so it cannot jump to an inner line. The outline, its fit before and after, and a picture."""
    return _err(L.follow, path, outline, radius_px=radius_px, smooth=smooth, mode=mode, picture=picture)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
