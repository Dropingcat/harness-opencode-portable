#!/usr/bin/env python3
"""cascade.py — каскад источников верификации (инкапсулированный модуль).

Порядок слоёв (приоритет/доступность, все проверены на диске):
  1. local_corpus — MCP literature_server.py, индекс literature_index.jsonl
     (424 источника, 34930 страниц). RU-термины обязательны (EN-покрытие ~0).
  2. openalex     — openalex_client.py (title/year/doi/venue/authors,
     abstract из abstract_inverted_index).
  3. arxiv        — search_arxiv.py (title/id/abstract/date).
  4. web_ddg      — ddg-search.py (title/href/snippet; полный текст НЕдоступен).
  5. scibot       — платный резерв: только по явному запросу (--use-scibot)
     или --simulate для тестов.

Правила каскада (по verification-plan.md, B.2):
  - остановка при >=2 независимых внешних подтверждениях или >=1 опровержении;
  - doom-loop: макс 3 итерации; при 0 результатов — упростить запрос;
  - каждый источник несёт provenance: found_via, origin (выставляется позже
    circularity.py), doi, url, relevance, accepted.

Модуль самодостаточен: не зависит от пайплайна, тестируется отдельно.

CLI:
  python3 cascade.py "laser nitriding accelerated nitride phase formation"
  python3 cascade.py "ускорение нитридообразования при лазерном азотировании" --layers local_corpus,openalex
  python3 cascade.py --simulate-scibot
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_HERMES_HOME = "/home/orangepi/.hermes/profiles/resercher"
OPENALEX_CLIENT = Path(
    "/home/orangepi/.hermes/profiles/resercher/skills/research/"
    "paper-orchestra/literature-review-agent/scripts/openalex_client.py"
)
ARXIV_SCRIPT = Path(
    "/home/orangepi/.hermes/profiles/resercher/skills/research/arxiv/scripts/search_arxiv.py"
)
DDG_SCRIPT = Path("/home/orangepi/.hermes/scripts/ddg-search.py")
DDG_PYTHON = os.environ.get("DDG_PYTHON", "python3.10")
PYTHON = os.environ.get("PYTHON", sys.executable)

STOP_AT_CONFIRMATIONS = 2
MAX_ITERATIONS = 3
MIN_CONFIRM_RELEVANCE = 0.5  # для остановки каскада нужны >=2 подтверждения с релевантностью >= этого
# Порог релевантности по слоям (доля значимых терминов запроса в тексте источника).
LOCAL_OVERLAP = 0.3
OPENALEX_OVERLAP = 0.4
ARXIV_OVERLAP = 0.4
WEB_OVERLAP = 0.2

RU_EN_GLOSSARY = {
    "ускорение": "acceleration",
    "нитридообразование": "nitride formation",
    "нитрид": "nitride",
    "азотирование": "nitriding",
    "лазерн": "laser",
    "вакуумн": "vacuum",
    "диффузи": "diffusion",
    "микродеформац": "microdeformation",
    "деформац": "deformation",
    "фаза": "phase",
    "сталь": "steel",
    "стал": "steel",
    "желез": "iron",
    "сплав": "alloy",
    "комбинирован": "combined",
    "обработк": "treatment",
    "рентген": "x-ray",
    "дифракц": "diffraction",
    "математическ": "mathematical",
    "регуляризац": "regularization",
    "параметр решетки": "lattice parameter",
    "дислокацион": "dislocation",
    "твёрдост": "hardness",
    "износостойк": "wear resistance",
    "поверхност": "surface",
}

_STOPWORDS_RU = {
    "при", "для", "и", "в", "на", "с", "со", "по", "из", "от", "о", "об", "не",
    "или", "что", "это", "как", "так", "уже", "быть", "данн", "котор",
}
_STOPWORDS_EN = {
    "the", "a", "an", "of", "and", "in", "on", "to", "for", "with", "that",
    "is", "are", "as", "by", "at", "from", "via", "using", "during",
}

_INDEX_CACHE = None


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def significant_terms(text, lang="auto", min_len=4):
    """Значимые термины текста (минус стоп-слова), для построения запросов."""
    t = norm_text(text)
    t = re.sub(r"[^a-zа-яё0-9\s-]", " ", t)
    words = []
    for w in re.split(r"[\s-]+", t):
        if not w or len(w) < min_len:
            continue
        if w in _STOPWORDS_RU or w in _STOPWORDS_EN:
            continue
        words.append(w)
    return words


def build_queries(claim_text, claim_class=None):
    """Строит RU + EN запросы из claim-текста.

    - local_corpus ищет по RU-терминам (EN-покрытие индекса ~0);
    - openalex/arxiv/web ищут по EN-терминам (заголовки научных статей).
    Для gap-claims добавляется маркер 'gap/unsolved/challenge'.
    """
    words = significant_terms(claim_text)
    ru_terms = []
    en_terms = []
    for w in words:
        if re.search(r"[а-яё]", w):
            ru_terms.append(w)
        else:
            en_terms.append(w)
    # дополняем EN-словарь из глоссария для RU-терминов
    for ru in ru_terms:
        for stem, en in RU_EN_GLOSSARY.items():
            if ru.startswith(stem):
                en_terms.extend(en.split())
                break
    # дедуп, сохраняя порядок
    def dedup(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    ru_terms, en_terms = dedup(ru_terms), dedup(en_terms)
    ru_q = " ".join(ru_terms) if ru_terms else claim_text[:120]
    en_q = " ".join(en_terms) if en_terms else claim_text[:120]
    if claim_class == "gap":
        ru_q = ru_q + " нерешённая задача"
        en_q = en_q + " unsolved challenge"
    return ru_q.strip(), en_q.strip()


def simplify_query(query):
    """Упрощение запроса для doom-loop: убрать самое длинное слово."""
    parts = [p for p in re.split(r"\s+", query.strip()) if p]
    if len(parts) <= 2:
        return query
    parts = sorted(parts, key=len, reverse=True)
    return " ".join(parts[1:])


# ── Слой 1: локальный корпус ──────────────────────────────────────────
def _load_literature_index(hermes_home=None):
    """Загружает индекс локального корпуса (реальный literature_server.py).

    Использует тот же источник данных, что и MCP literature_server:
    индекс в HERMES_HOME/cache/literature/literature_index.jsonl.
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    candidates = []
    if hermes_home:
        candidates.append(hermes_home)
    candidates.append(os.environ.get("HERMES_HOME", ""))
    candidates.append(DEFAULT_HERMES_HOME)
    idx_path = None
    for hh in candidates:
        if not hh:
            continue
        p = Path(hh) / "cache" / "literature" / "literature_index.jsonl"
        if p.is_file():
            idx_path = p
            break
    recs = []
    if idx_path is not None:
        with idx_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    _INDEX_CACHE = recs
    return recs


def _score_page(page_text, terms):
    """Доля значимых терминов запроса, присутствующих на странице."""
    t = page_text.lower()
    present = sum(1 for term in terms if term in t)
    return present / len(terms) if terms else 0.0


def search_local_corpus(query, limit=4, per_source=1, hermes_home=None,
                        min_overlap=LOCAL_OVERLAP):
    """Полнотекстовый поиск по локальному корпусу (реальный индекс).

    Возвращает нормализованные записи с found_via="local_corpus".
    Поиск мягче, чем в literature_server._search: достаточно части терминов.
    """
    terms = [t for t in re.split(r"\s+", query.lower()) if len(t) >= 3]
    if not terms:
        return []
    recs = _load_literature_index(hermes_home)
    scored = []
    for rec in recs:
        s = _score_page(rec.get("text", ""), terms)
        if s >= min_overlap:
            scored.append((s, rec))
    scored.sort(key=lambda x: -x[0])
    grouped = {}
    for s, rec in scored:
        grouped.setdefault(rec["path"], []).append((s, rec))
    out = []
    for path, items in grouped.items():
        for s, rec in items[:per_source]:
            snippet = _make_snippet(rec.get("text", ""), query, 400)
            out.append({
                "title": rec.get("name", path),
                "type": "textbook",
                "trust": 0.7,
                "excerpt": snippet,
                "text": rec.get("text", "")[:1000],
                "year": None,
                "doi": "",
                "url": None,
                "authors": [],
                "venue": "local_corpus",
                "found_via": "local_corpus",
                "found_query": query,
                "origin": "external",
                "relevance": round(s, 3),
                "accepted": s >= min_overlap,
                "page": rec.get("page"),
            })
        if len(out) >= limit:
            break
    return out[:limit]


def _make_snippet(text, query, width=400):
    t = norm_text(text)
    terms = [x for x in re.split(r"\s+", query.lower()) if len(x) >= 3]
    idx = -1
    for term in terms:
        p = t.find(term)
        if p != -1:
            idx = p if idx == -1 else min(idx, p)
    if idx == -1:
        return t[:width]
    start = max(0, idx - width // 2)
    return ("…" if start > 0 else "") + t[start:start + width] + ("…" if start + width < len(t) else "")


# ── Слой 2: OpenAlex ──────────────────────────────────────────────────
def _reconstruct_abstract(inverted_index):
    """Восстанавливает абстракт из abstract_inverted_index OpenAlex."""
    if not isinstance(inverted_index, dict):
        return ""
    pos = {}
    for word, positions in inverted_index.items():
        for p in positions:
            pos[p] = word
    if not pos:
        return ""
    return " ".join(pos[i] for i in sorted(pos))


def _openalex_query(url, timeout=30, max_retries=3):
    """Запрос к OpenAlex с retry/backoff при HTTP 429 (rate limit). P2.3."""
    import urllib.error  # локальный импорт для HTTPError
    last_exc = None
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "claimeai-verification/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                backoff = 2 ** attempt  # 2, 4 сек
                print(f"openalex 429: retry {attempt}/{max_retries} после {backoff}с", file=sys.stderr)
                time.sleep(backoff)
                last_exc = e
                continue
            raise
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise
    raise last_exc


def search_openalex(query, limit=5, mailto="", min_overlap=OPENALEX_OVERLAP):
    """Поиск по OpenAlex Works API (реальный модуль openalex_client.py).

    Использует тот же endpoint и User-Agent-политику. Возвращает записи с
    found_via="openalex" и восстановленным абстрактом.
    """
    params = {"search": query, "per-page": min(25, max(1, limit))}
    if mailto or os.environ.get("OPENALEX_MAILTO"):
        params["mailto"] = mailto or os.environ.get("OPENALEX_MAILTO")
    url = f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}"
    terms = significant_terms(query, lang="en")
    try:
        data = _openalex_query(url)
    except Exception as exc:
        return [{"error": f"openalex: {exc}", "found_via": "openalex"}]
    out = []
    for w in data.get("results", []) or []:
        title = w.get("title") or w.get("display_name") or ""
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
        hay = norm_text(f"{title} {abstract}")
        if terms:
            overlap = sum(1 for t in terms if t in hay) / len(terms)
        else:
            overlap = 1.0
        if overlap < min_overlap:
            continue
        doi = (w.get("doi") or "").replace("https://doi.org/", "").replace("http://doi.org/", "")
        src = ((w.get("primary_location") or {}).get("source") or {})
        authors = [(a.get("author") or {}).get("display_name", "")
                   for a in w.get("authorships", []) or []]
        out.append({
            "title": title,
            "type": "journal_article",
            "trust": 0.75,
            "excerpt": abstract[:500] or title,
            "text": abstract or title,
            "year": w.get("publication_year"),
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else None,
            "authors": [a for a in authors if a],
            "venue": src.get("display_name", ""),
            "found_via": "openalex",
            "found_query": query,
            "origin": "external",
            "relevance": round(overlap, 3),
            "accepted": overlap >= min_overlap,
        })
    return out[:limit]


# ── Слой 3: arXiv ─────────────────────────────────────────────────────
_ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}


def search_arxiv(query, limit=5, min_overlap=ARXIV_OVERLAP):
    """Поиск по arXiv API (реальный endpoint search_arxiv.py).

    Возвращает записи с found_via="arxiv".
    """
    params = {
        "search_query": f"all:{urllib.parse.quote(query)}",
        "max_results": str(max(1, limit)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": "HermesAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            root = ET.fromstring(resp.read())
    except Exception as exc:
        return [{"error": f"arxiv: {exc}", "found_via": "arxiv"}]
    terms = significant_terms(query, lang="en")
    out = []
    for entry in root.findall("a:entry", _ARXIV_NS):
        title = (entry.findtext("a:title", "", _ARXIV_NS) or "").strip().replace("\n", " ")
        abstract = (entry.findtext("a:summary", "", _ARXIV_NS) or "").strip().replace("\n", " ")
        full_id = (entry.findtext("a:id", "", _ARXIV_NS) or "").strip()
        arxiv_id = full_id.split("/abs/")[-1].split("v")[0] if "/abs/" in full_id else full_id.split("v")[0]
        published = (entry.findtext("a:published", "", _ARXIV_NS) or "")[:10]
        hay = norm_text(f"{title} {abstract}")
        if terms:
            overlap = sum(1 for t in terms if t in hay) / len(terms)
        else:
            overlap = 1.0
        if overlap < min_overlap:
            continue
        authors = [a.findtext("a:name", "", _ARXIV_NS) for a in entry.findall("a:author", _ARXIV_NS)]
        out.append({
            "title": title,
            "type": "preprint",
            "trust": 0.6,
            "excerpt": abstract[:500],
            "text": abstract,
            "year": int(published[:4]) if published else None,
            "doi": "",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "authors": [a for a in authors if a],
            "venue": "arXiv",
            "found_via": "arxiv",
            "found_query": query,
            "origin": "external",
            "relevance": round(overlap, 3),
            "accepted": overlap >= min_overlap,
        })
    return out[:limit]


# ── Слой 4: Веб (DDG) ────────────────────────────────────────────────
def search_web(query, limit=4, min_overlap=WEB_OVERLAP):
    """Поиск по вебу через DDG (реальный скрипт ddg-search.py, --json).

    Возвращает title/href/snippet. Полный текст недоступен (search-only);
    для stance достаточно сниппета + href.
    """
    script = str(DDG_SCRIPT)
    if not Path(script).is_file():
        return [{"error": f"web: ddg-скрипт не найден: {script}", "found_via": "web_search"}]
    try:
        proc = subprocess.run(
            [DDG_PYTHON, script, query, "--count", str(limit), "--json"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:
        return [{"error": f"web: {exc}", "found_via": "web_search"}]
    try:
        results = json.loads((proc.stdout or "").strip())
    except (json.JSONDecodeError, ValueError):
        if "error" in (proc.stderr or "").lower():
            return [{"error": f"web: {proc.stderr.strip()[:200]}", "found_via": "web_search"}]
        return [{"error": "web: не удалось распарсить DDG-выдачу", "found_via": "web_search"}]
    terms = significant_terms(query, lang="en") or significant_terms(query)
    out = []
    for r in results or []:
        title = r.get("title", "")
        href = r.get("href", "")
        body = r.get("body", "")
        hay = norm_text(f"{title} {body}")
        if terms:
            overlap = sum(1 for t in terms if t in hay) / len(terms)
        else:
            overlap = 1.0
        if overlap < min_overlap:
            continue
        out.append({
            "title": title,
            "type": "web_page",
            "trust": 0.4,
            "excerpt": body[:500],
            "text": body,
            "year": None,
            "doi": "",
            "url": href,
            "authors": [],
            "venue": "",
            "found_via": "web_search",
            "found_query": query,
            "origin": "external",
            "relevance": round(overlap, 3),
            "accepted": overlap >= min_overlap,
        })
    return out[:limit]


# ── Слой 5: sci-bot (платный резерв) ─────────────────────────────────
def search_scibot(query, simulate=False, question=None):
    """Платный резервный слой. По умолчанию — не тратит токены.

    - simulate=True: правдоподобный ответ (тест парсинга, 0 токенов).
    - иначе: возвращает запись "не вызывается" (безопасно по умолчанию).
    """
    if not simulate:
        return [{
            "error": "scibot: платный резерв, не вызывается без --use-scibot/--simulate",
            "found_via": "scibot",
        }]
    q = question or query
    return [{
        "title": f"Sci-Bot (simulate): {q[:60]}",
        "type": "scihub_fulltext",
        "trust": 0.5,
        "excerpt": "Симуляция sci-bot ответа: найден релевантный источник "
                   "по запросу. DOI: 10.1016/j.actamat.2026.000001.",
        "text": "Симуляция sci-bot ответа.",
        "year": 2026,
        "doi": "10.1016/j.actamat.2026.000001",
        "url": "https://doi.org/10.1016/j.actamat.2026.000001",
        "authors": [],
        "venue": "sci-bot",
        "found_via": "scibot",
        "found_query": query,
        "origin": "external",
        "relevance": 0.8,
        "accepted": True,
    }]


# ── Каскад ────────────────────────────────────────────────────────────
# ── Слой 4.5: Веб через browser-MCP (Playwright, anti-bot) ─────────
# browser-mcp даёт полный текст страниц (в отличие от DDG-search-only).
# Используется как fallback/подтверждение когда DDG недоступен (anti-bot)
# или нужно извлечь полный текст URL для stance.
def search_web_browser(query, limit=4, min_overlap=WEB_OVERLAP):
    """Поиск по вебу через browser-MCP (mcp_browser_server.py, browser_search).

    Запускает MCP-капсулу как подпроцесс и извлекает результаты DDG через
    Playwright (обход anti-bot). Возвращает title/url/snippet.
    """
    browser_py = os.environ.get(
        "BROWSER_MCP_PYTHON", "/home/orangepi/.hermes/venvs/browser-mcp/bin/python")
    server_script = os.environ.get(
        "BROWSER_MCP_SERVER", "/home/orangepi/scripts/mcp_browser_server.py")
    if not Path(server_script).is_file():
        return [{"error": f"web_browser: скрипт не найден: {server_script}", "found_via": "web_search"}]
    if not Path(browser_py).is_file():
        return [{"error": f"web_browser: python не найден: {browser_py}", "found_via": "web_search"}]
    # Внутри MCP-капсулы есть функция browser_search; вызываем через её CLI-подобный режим.
    # Простейший надёжный путь: browser_search в mcp_browser_server.py — функция, не CLI.
    # Для cascade достаточно DDG через Playwright; browser_search в капсуле — Python-функция.
    # Здесь используем прямой вызов: python -c "import mcp_browser_server; ..." — тяжёлый (Playwright).
    # Ограничиваем: browser-слой вызывается ТОЛЬКО при --use-scibot-подобном флаге (не по умолчанию),
    # чтобы не тормозить каждый прогон запуском Chromium.
    try:
        # Пытаемся использовать browser_search; при недоступности — fallback на error-запись.
        code = (
            "import sys, json, asyncio; "
            "sys.path.insert(0, '/home/orangepi/scripts'); "
            "import importlib.util; "
            "spec=importlib.util.spec_from_file_location('b', '/home/orangepi/scripts/mcp_browser_server.py'); "
            "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            f"r=m.browser_search('{query.replace(chr(39),'')}', 'ddg'); "
            "print(json.dumps(r, ensure_ascii=False))"
        )
        proc = subprocess.run([browser_py, "-c", code], capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return [{"error": f"web_browser: rc={proc.returncode}: {(proc.stderr or '')[:200]}", "found_via": "web_search"}]
        data = json.loads((proc.stdout or "").strip())
        results = data if isinstance(data, list) else data.get("results", [])
        terms = significant_terms(query, lang="en") or significant_terms(query)
        out = []
        for r in results or []:
            title = r.get("title", "")
            href = r.get("url") or r.get("href", "")
            body = r.get("snippet", "") or r.get("description", "")
            hay = norm_text(f"{title} {body}")
            if terms:
                overlap = sum(1 for t in terms if t in hay) / len(terms) if terms else 0.0
            else:
                overlap = 1.0
            if overlap < min_overlap:
                continue
            out.append({
                "title": title, "type": "web_page", "trust": 0.4,
                "excerpt": body[:500], "text": body, "year": None, "doi": "",
                "url": href, "authors": [], "venue": "",
                "found_via": "web_browser", "found_query": query,
                "origin": "external", "relevance": round(overlap, 3),
                "accepted": overlap >= min_overlap,
            })
        return out[:limit]
    except Exception as exc:
        return [{"error": f"web_browser: {exc}", "found_via": "web_search"}]


LAYER_ORDER = ["local_corpus", "openalex", "arxiv", "web_ddg", "scibot"]

LAYER_FUNCS = {
    "local_corpus": search_local_corpus,
    "openalex": search_openalex,
    "arxiv": search_arxiv,
    "web_ddg": search_web,
    "web_browser": search_web_browser,
    "scibot": search_scibot,
}


def _external_accepts(results):
    """Результаты слоя, принятые как внешние подтверждения (без ошибок)."""
    return [r for r in results
            if r.get("accepted") and not r.get("error")]


def _confirmations(sources):
    """Достаточно сильные подтверждения для остановки каскада."""
    return [r for r in sources
            if r.get("accepted") and not r.get("error")
            and (r.get("relevance") or 0.0) >= MIN_CONFIRM_RELEVANCE]


def run_cascade(query, layers=None, use_scibot=False, simulate_scibot=False,
                max_iterations=MAX_ITERATIONS,
                stop_at=STOP_AT_CONFIRMATIONS,
                question=None):
    """Прогон каскада по одному запросу.

    Возвращает {"sources": [...], "verification_meta": {...}}.
    Останавливается при >=stop_at независимых внешних подтверждениях
    или >=1 опровержении (обнаружение опровержения — на стороне verifier).
    Doom-loop: макс max_iterations итераций, при 0 результатов — упрощение запроса.
    """
    if layers is None:
        layers = LAYER_ORDER
    layers = [l for l in layers if l != "scibot"] + (["scibot"] if use_scibot or simulate_scibot else [])
    sources = []
    used = []
    queries = [query]
    iterations = 0
    cur_query = query
    budget_tokens = 0

    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        before = len([r for r in sources if r.get("accepted") and not r.get("error")])
        for layer in layers:
            if layer in used:
                continue
            func = LAYER_FUNCS[layer]
            kwargs = {"query": cur_query}
            if layer == "scibot":
                kwargs = {"query": cur_query, "simulate": simulate_scibot, "question": question}
            results = func(**kwargs)
            used.append(layer)
            accepted = _external_accepts(results)
            for r in results:
                if r.get("error"):
                    continue
                r["found_query"] = cur_query
                sources.append(r)
            if accepted:
                queries.append(cur_query)
            if layer == "scibot" and simulate_scibot:
                budget_tokens = 0
            if len(_confirmations(sources)) >= stop_at:
                return _cascade_result(sources, used, queries, iterations, budget_tokens)
        # конец прохода по слоям: если достаточно — стоп
        if len(_confirmations(sources)) >= stop_at:
            break
        # doom-loop: при 0 результатов упрощаем запрос и повторяем слои заново
        if len(_confirmations(sources)) == 0:
            simpler = simplify_query(cur_query)
            if simpler == cur_query:
                break
            cur_query = simpler
            used = []
        else:
            break

    return _cascade_result(sources, used, queries, iterations, budget_tokens)


def _cascade_result(sources, used, queries, iterations, budget_tokens):
    accepted = [r for r in sources if r.get("accepted") and not r.get("error")]
    external = [r for r in accepted if r.get("origin") == "external"]
    return {
        "sources": sources,
        "verification_meta": {
            "cascade_used": used,
            "external_found": len(external),
            "document_derived_found": len([r for r in accepted if r.get("origin") != "external"]),
            "queries_used": queries,
            "iterations": iterations,
            "budget_tokens": budget_tokens,
        },
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="?", help="поисковый запрос")
    ap.add_argument("--layers", default=",".join(LAYER_ORDER),
                    help="слои каскада через запятую (по умолчанию все)")
    ap.add_argument("--limit", type=int, default=4)
    ap.add_argument("--use-scibot", action="store_true")
    ap.add_argument("--simulate-scibot", action="store_true")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    if not args.query:
        ap.print_help()
        sys.exit(2)

    layers = [l.strip() for l in args.layers.split(",") if l.strip()]
    res = run_cascade(
        args.query,
        layers=layers,
        use_scibot=args.use_scibot,
        simulate_scibot=args.simulate_scibot,
    )
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        meta = res["verification_meta"]
        print(f"Каскад: {meta['iterations']} итер., слои {meta['cascade_used']}")
        print(f"Внешних принято: {meta['external_found']}, циркулярных: {meta['document_derived_found']}")
        for i, s in enumerate(res["sources"], 1):
            if s.get("error"):
                print(f"  {i}. [ошибка] {s['error']}")
                continue
            print(f"  {i}. [{s['found_via']}] {s['title'][:80]} | rel={s.get('relevance')} "
                  f"| doi={s.get('doi') or '-'} | {s.get('url') or ''}")


if __name__ == "__main__":
    main()