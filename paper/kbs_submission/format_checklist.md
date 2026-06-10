# KBS Format Compliance Checklist

- [x] Title: <= 150 characters (current: 127, OK)
- [x] Abstract: <= 250 words (current: ~220 words after expansion, OK)
- [x] Keywords: 4-6 provided (current: 6, OK)
- [x] Manuscript length: <= 20 pages (current: 17 pages after compilation, OK)
- [x] Figures: >= 300 DPI, all 5 main PNG figures verified at 299.9994 DPI (OK)
- [ ] Figure color space: verify production requirement if CMYK is required (PNG source is RGB; Elsevier accepts RGB for review)
- [x] Tables: numbered, with captions above, cross-referenced in text (OK)
- [x] References: Elsevier numbered style [1], [2] with `cas-model2-names.bst`, 41 cited entries, compiled and verified
- [x] Supplementary materials: described in Data Availability (OK)
- [x] Cover letter: anonymous, no author info (current: generated)
- [x] CRediT authorship contribution statement: added (anonymous)
- [x] Acknowledgments: added
- [x] Competing interests: declared (current: "no known competing", OK)
- [x] BibTeX warnings: 0 warnings (12 empty-pages warnings resolved by adding pages to all inproceedings entries)
- [x] Overfull/Underfull hboxes: 0 content-level warnings (minor 117pt CAS class internal overfull at \maketitle is a known class-file artifact unrelated to content; confirmed by test with trivial title)
- [x] Compilation: clean pass pdflatex → bibtex → pdflatex ×2, 0 errors
