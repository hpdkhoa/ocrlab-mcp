# Changelog

## 0.2.0

* Lines in a picture (`ocrlab.lines`, the `lines` extra: opencv-python, numpy). `line_map`: the line art's ink
  middles (or a photo's Canny edges) as a cost map, px to the nearest line. `fit`: how far an outline sits off the
  lines (mean, 95th percentile, largest, share within 1.5 px). `follow`: a rough outline laid onto the lines as one
  line: each point moves only along its normal, all moves chosen together by dynamic programming round the closed
  outline, then a sub-pixel step; a picture colours each point by its miss.
* `follow` returns a simple outline: `untangle` cuts each loop off at its crossing and keeps the larger part (a
  solid built from a crossing outline is broken). `crossings` counts them.
* Tools: `line_fit`, `line_follow`.
* Photos are read at their strong edges: Canny on the gradient, its high threshold at the 94th percentile, weak edges
  kept where they join a strong one. The follower's cost is capped at 12 px, so a stretch with no line in reach stays
  where it was read. `follow` gives `area_change` so a caller can refuse an outline that collapsed.
* Measured on an M16A2 side view (TM line art): seven parts read by eye sat 7 to 21 px off the lines (95th
  percentile), 1 to 5 px after `follow`. On an M82A2 photo on a wood floor: 7 to 24 px before, 1 to 6 px after.

## 0.1.0

* A PDF page is read from its text layer when it has one, else rendered and read by Tesseract.
* Every line and word comes back with its box on the page (PDF points from the top left) and, for OCR, Tesseract's
  confidence. Pages are cached by the file's path, size and time.
* Tools: `pdf_info`, `read_page`, `read_pages`, `find`, `words_in`, `read_image`. A command line: `ocrlab`.
