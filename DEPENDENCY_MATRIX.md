# Dependency matrix

| Capability | Primary implementation | Optional/fallback | Preflight behavior |
|---|---|---|---|
| web.discovery | SearXNG (native, `127.0.0.1:8888`) + `search_gateway.py` | academic API route | backend liveness probed via HTTP JSON |
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
| Tesseract OCR | **installed** (2026-09-08) | 5.4.0.20240606 (UB-Mannheim, leptonica 1.84.1) | `C:\Program Files\Tesseract-OCR\` | `eng`, `osd` + `rus`, `equ` (tessdata_fast) | added to **User** PATH |
| LibreOffice | not installed (optional) | — | — | — | probed, missing = `office.legacy.inspect` stays `missing` |

## SearXNG service

SearXNG is a **service backend** (HTTP JSON API on `127.0.0.1:8888`), not a pip package of the
capability overlay. It was installed natively (no Docker/WSL available) from
`https://github.com/searxng/searxng.git` into `E:\Documents\searxng\`:

- venv: `E:\Documents\searxng\.venv` (deps from `requirements.txt`; `tzdata` added for Windows zoneinfo)
- source: `E:\Documents\searxng\searxng-src` (editable install `pip install --no-build-isolation -e .`)
- settings: `searxng-src\searx\settings.yml` — `server.port: 8888`, `bind_address: 127.0.0.1`,
  `search.formats: [html, json]`, `limiter: false`, generated `secret_key`
- control: `start-searxng.ps1` / `stop-searxng.ps1`; Windows Task Scheduler task **`SearXNG`**
  (`/sc onstart`) restarts it after reboot
- Windows patch: `searx/valkeydb.py` guards `import pwd` (Unix-only; unused while `valkey.url` is
  false). Optional `searxng_extra` Lua/updater tooling is not installed.

Preflight: `existing.searxng` live-probes `http://127.0.0.1:8888/search?...&format=json`;
`local.search_gateway` uses the same URL. With the service up, `web.discovery` resolves
`available` and the `academic-research` `required_any_of: [web.discovery, academic.metadata]`
group is satisfied by either leg.

Notes:
- Tesseract is an **external binary**, not a Python package: it is not declared in
  `requirements-capability-bundle.txt` and is not installed via pip. Preflight detects it by
  resolving `tesseract` on PATH (`local.ocr` provider → `document.ocr` capability).
- Removing Tesseract (or removing it from PATH) downgrades `document.ocr` to `missing` and
  correctly denies `document.ocr` capability escalation — no Python code breaks.
- Installer used: UB-Mannheim NSIS bundle v5.4.0.20240606 (`tesseract-ocr-w64-setup-5.4.0.20240606.exe`).
- Russian OCR: `rus.traineddata` + `equ.traineddata` (equations) from `tessdata_fast` were added to
  `tessdata/`. Language key for OCR calls: `-l rus` (fall back to `-l eng` when input is Latin).
  Existing text-layer extraction (`document_inspect.py` PDF path) is untouched; OCR is the separate
  `document.ocr` capability for scanned/no-text-layer pages.
