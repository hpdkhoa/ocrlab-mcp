# Changelog

## 0.1.0

* A PDF page is read from its text layer when it has one, else rendered and read by Tesseract.
* Every line and word comes back with its box on the page (PDF points from the top left) and, for OCR, Tesseract's
  confidence. Pages are cached by the file's path, size and time.
* Tools: `pdf_info`, `read_page`, `read_pages`, `find`, `words_in`, `read_image`. A command line: `ocrlab`.
