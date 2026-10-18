"""ocrlab <command>
  serve                              the MCP server (also: ocrlab-mcp)
  info <pdf>                         pages, text layers, what needs OCR
  page <pdf> <n> [--ocr]             one page's text (--ocr: read it by OCR even with a text layer)
  find <pdf> <pattern> [pages]       lines matching a regular expression"""
import json
import sys


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if a[0] == "serve":
        from .server import main as serve
        serve()
        return 0
    from . import read as R
    if a[0] == "info":
        print(json.dumps(R.info(a[1]), indent=1))
        return 0
    if a[0] == "page":
        r = R.page(a[1], int(a[2]), force_ocr="--ocr" in a)
        print("page %d (%s, mean confidence %s)\n%s" % (r["page"], r["source"], r["mean_conf"], r["text"]))
        return 0
    if a[0] == "find":
        for h in R.find(a[1], a[2], pages=a[3] if len(a) > 3 else None):
            print("p%-4d %s" % (h["page"], h["line"]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
