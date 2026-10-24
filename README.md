<h1 align="center">OCR Lab</h1>

<!-- mcp-name: io.github.hpdkhoa/ocrlab-mcp -->

<p align="center"><strong>Scanned documents, read: a PDF page's own text when it has some, Tesseract OCR when it has not, every word with its box and its confidence.</strong></p>

Old manuals, patents and data sheets are often scans: pictures of pages with no text in them. OCR Lab reads them.
A page with a text layer is read from it. A page without one is rendered and read by
[Tesseract](https://github.com/tesseract-ocr/tesseract). Every line and word comes back with its box on the page, in
PDF points from the top left, and with Tesseract's confidence from 0 to 100. A number can then be found next to its
label and checked on the page picture.

OCR misreads. It read "lb" as "1b" and "folded" as "felded" on a 1970s army scan. Check every number you keep on the
page itself.

## Install

1. Install Tesseract 5: on Windows the UB Mannheim build, on macOS `brew install tesseract`, on Linux
   `apt install tesseract-ocr`. OCR Lab finds it on the PATH, in the usual install folders, or at `OCRLAB_TESSERACT`.
2. `pip install ocrlab-mcp`
3. Add it to your MCP client: `claude mcp add ocrlab -- ocrlab-mcp`

OCR Lab writes only to `OCRLAB_OUT` (default `~/.ocrlab`): its cache of read pages.

## Tools

| Tool | What it does |
|---|---|
| `pdf_info` | The page count, which pages have a text layer and which need OCR, and where Tesseract is. |
| `read_page` | One page's text and lines, with boxes and confidence; `words` adds every word. |
| `read_pages` | Several pages read and cached, with each page's source and mean confidence. |
| `find` | Every line matching a regular expression, with its page, box and the lines round it. |
| `words_in` | The words inside a box on a page: one column of a table read on its own. |
| `read_image` | An image file read by Tesseract. |
| `line_fit` | How far an outline (px) sits off a drawing's lines: mean, 95th percentile, largest miss, share on a line. |
| `line_follow` | A rough outline laid onto a drawing's lines as one line, with its fit before and after and a picture. |

## Lines in drawings

`pip install ocrlab-mcp[lines]` adds a line reader for line art and photos. `line_follow` moves each point of a
rough outline only along its own normal and picks all the moves together (dynamic programming round the closed
outline), each point on a line's middle and neighbours moving alike. An outline therefore stays on one line: it does not
jump to an inner line and back, and does not slide along a line. Its picture shows each point green on a line and
red off it, so a miss is seen, not hidden.

## Command line

```
ocrlab info manual.pdf
ocrlab page manual.pdf 5
ocrlab find manual.pdf "overall length|weight" 1-12
```

## Licence

MIT. Tesseract is Apache 2.0 and installed on its own.
