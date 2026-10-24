# Changelog

## 0.2.0

* Lines in a picture (`ocrlab.lines`, the `lines` extra: opencv-python, numpy). `line_map`: the line art's ink
  middles (or a photo's Canny edges) as a cost map, px to the nearest line. `fit`: how far an outline sits off the
  lines (mean, 95th percentile, largest, share within 1.5 px). `follow`: a rough outline laid onto the lines as one
  line: each point moves only along its normal, all moves chosen together by dynamic programming round the closed
  outline, then a sub-pixel step; a picture colours each point by its miss.
* Tools: `line_fit`, `line_follow`.
* Measured on an M16A2 side view (TM line art): seven parts' outlines that sat 6 to 21 px off the lines (95th
  percentile) sit 1.2 to 4.9 px off after `follow`.

## 0.1.0

* A PDF page is read from its text layer when it has one, else rendered and read by Tesseract.
* Every line and word comes back with its box on the page (PDF points from the top left) and, for OCR, Tesseract's
  confidence. Pages are cached by the file's path, size and time.
* Tools: `pdf_info`, `read_page`, `read_pages`, `find`, `words_in`, `read_image`. A command line: `ocrlab`.
