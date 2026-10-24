"""OCR Lab: the text of scanned documents, read where a page has no text of its own. A PDF page's text layer is used
when it has one; a page without one is rendered and read by Tesseract. Every word comes with its box on the page and
its confidence, so a number can be found next to its label and checked on the page picture. Drawings are read too: where their
lines are, and an outline laid onto them (lines)."""
__version__ = "0.2.0"
