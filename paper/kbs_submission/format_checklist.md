# KBS Format Compliance Checklist

- [x] Title: 119 characters, within the 150-character working target.
- [x] Abstract: 217 words, within the 250-word working target.
- [x] Keywords: 6 provided.
- [x] Final tracked PDF generated from synchronized source: `main.pdf`, 37 pages, 630071 bytes.
- [x] Claim-safe PDF text scan: no positive GSM8K/HotpotQA downstream filtering, PRM training, replay-validation, or external-generalization claim found.
- [x] Figures/tables/algorithms: 6 figure environments, 14 table environments, and 2 algorithms compile in the final PDF.
- [x] Current `main.tex` does not directly include PNG figures; retained PNG files are historical/supplementary assets and are not cited as current positive validation results.
- [ ] Figure color space: production CMYK requirements were not revalidated in this pass; PNG source assets remain RGB where retained.
- [x] References: Elsevier numbered style via `cas-model2-names.bst`; BibTeX completed during final `latexmk` build.
- [x] Supplementary materials: PRM800K v3.6/v3.8 evidence entries and failed-route provenance are listed in the supplement descriptions and manifest.
- [x] Cover letter: anonymous and synchronized to the v3.6/v3.8 claim boundary.
- [x] CRediT authorship contribution statement: present and anonymous.
- [x] Acknowledgments: present.
- [x] Competing interests: declared as no known competing interests.
- [x] Compilation: `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` completed with exit code 0.
- [x] LaTeX warnings reviewed: no undefined references or citation failures in the final log; remaining warnings are float default-placement notices, a hyperref empty-anchor warning at title generation, duplicate-destination warnings from appendix counter resets, and overfull boxes from long numeric/path/table content.
