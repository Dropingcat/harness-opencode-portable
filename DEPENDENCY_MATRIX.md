# Dependency matrix

| Capability | Primary implementation | Optional/fallback | Preflight behavior |
|---|---|---|---|
| web.discovery | existing SearXNG MCP + `search_gateway.py` | academic API route | wrapper existing but backend down = degraded |
| academic.metadata | existing OpenAlex/arXiv + `source_resolve.py` | Crossref | network unavailable = degraded |
| source.oa_resolve | Unpaywall in source resolver | none | requires network and `UNPAYWALL_EMAIL` for actual lookup |
| PDF | PyMuPDF | existing doc MCP | package missing = fallback/provider downgrade |
| DOCX | python-docx | existing doc MCP | independent module probe |
| XLSX | openpyxl | future python-calamine/Excel COM | independent module probe |
| OCR | Tesseract | future OCRmyPDF wrapper | executable probe (external binary, see below) |
| legacy Office | LibreOffice | future Word/Excel COM | executable/platform probe |
| TIFF | tifffile | Pillow previews | metadata preserved, semantic vendor decode not claimed |
| scientific compute | SymPy | researcher-core units/uncertainty/formulas | deterministic local calculation |
| plotting | matplotlib | none | deterministic derived artifact |
| corpus | SQLite FTS5 | later DuckDB/vector layer | stdlib SQLite feature probe |
| evidence | existing code-factory/fact-checker | researcher-core bridge | gate, not extraction |
| code acceptance | existing Stage-3 factory | reviewer/tester/auditor | isolated acceptance remains existing authority |
| job/checkpoint | `job_ctl.py` | later distributed execution substrate | local atomic manifest |

Not bundled as hard dependencies yet: GROBID, OCRmyPDF, Docling, HyperSpy/RosettaSciIO, ExifTool, OpenCV, python-calamine. They should be registered as providers after standalone smoke tests on the target server, not advertised because their names look impressive in a config file.

## External (non-Python) system dependencies

These are not pip packages. They are installed as system binaries/programs on the target
server and are probed by the capability overlay with an `executable` probe (`shutil.which`).

| Dependency | Status | Version | Install location | Lang data | PATH |
|---|---|---|---|---|---|
| Tesseract OCR | **installed** (2026-09-08) | 5.4.0.20240606 (UB-Mannheim, leptonica 1.84.1) | `C:\Program Files\Tesseract-OCR\` | `eng`, `osd` (`tessdata/`) | added to **User** PATH |
| LibreOffice | not installed (optional) | — | — | — | probed, missing = `office.legacy.inspect` stays `missing` |

Notes:
- Tesseract is an **external binary**, not a Python package: it is not declared in
  `requirements-capability-bundle.txt` and is not installed via pip. Preflight detects it by
  resolving `tesseract` on PATH (`local.ocr` provider → `document.ocr` capability).
- Removing Tesseract (or removing it from PATH) downgrades `document.ocr` to `missing` and
  correctly denies `document.ocr` capability escalation — no Python code breaks.
- Installer used: UB-Mannheim NSIS bundle v5.4.0.20240606 (`tesseract-ocr-w64-setup-5.4.0.20240606.exe`).
