#!/usr/bin/env python3
"""techdebt_control.py — детерминированный контроль техдолга оркестратора.

Читает клейм-трекер RESEARCHER_CLAIMS.md (раздел «ГРАФ СВЯЗЕЙ ЗАДАЧ») и
опционально resercher-todo.md, строит граф узлов (слои 0-3), проверяет 7
инвариантов техдолга, выдаёт алерты (CRITICAL/WARNING), топосорт-порядок и
markdown/JSON-отчёт. Только stdlib: re, json, argparse, datetime, collections.

CLI:
  python3 techdebt_control.py --claims RESEARCHER_CLAIMS.md \
      [--todo resercher-todo.md] [--stale-days 14] [--json] [--report out.md]
Exit: 0 = чисто, 1 = есть CRITICAL/WARNING, 2 = ошибка ввода.
"""
import argparse
import json
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

# ── Инварианты и алерты ──────────────────────────────────────────────────
I1 = "I1-ORPHAN-RANK1"    # сирота ранга 1 (без связей никуда)
I2 = "I2-BROKEN-LINK"     # связь на несуществующий тег
I3 = "I3-DUPLICATE-TAG"   # дубль тега в источнике
I4 = "I4-RANK-DEGRADE"    # деградация ранга (1→3, 2→3) без причины
I5 = "I5-STALE"           # активный узел не обновлялся > N дней
I6 = "I6-DISCONNECTED"    # активная задача не связана с ранговым узлом 0
I7 = "I7-CYCLE"           # цикл зависимостей

SEVERITY = {
    I1: "CRITICAL", I2: "CRITICAL", I3: "WARNING", I4: "WARNING",
    I5: "WARNING", I6: "CRITICAL", I7: "WARNING",
}
INVARIANT_NAMES = {
    I1: "I1 нет сирот ранга 1",
    I2: "I2 нет битых связей",
    I3: "I3 нет дублей тегов",
    I4: "I4 ранги не деградируют",
    I5: "I5 нет застревания",
    I6: "I6 активная связана с ранговым узлом 0",
    I7: "I7 нет циклов зависимостей",
}
DEFAULT_STALE_DAYS = 14
WILDCARD_LINKS = {"все", "all", "*"}   # «все» = узел связан со всеми

# Семейства ID, документированные в трекере и смежных отчётах
# (todo-лист: H/M/N/D; дефекты C; роли R; траблы окружения T; числовые P).
_ID_FAMILIES = {
    "C": (1, 4), "H": (1, 4), "M": (1, 4), "N": (1, 3),
    "D": (1, 3), "R": (1, 4), "T": (1, 4), "P": (0, 10),
}
_REASON_MARKERS = ("понижен", "деград", "причин", "из-за", "ранее",
                   "был ранга", "changed", "degrad", "reason")
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TAGLINE_RE = re.compile(r"\[\s*тег\s*:\s*([^\]\[]+?)\s*\]")
_TODO_ID_RE = re.compile(r"^\s*#{2,4}\s+([A-Z]\d+)\b")
_TAGLIKE_RE = re.compile(r"^[0-9A-Za-zА-Яа-яЁё\-.]+$")


# ── Вспомогательные ──────────────────────────────────────────────────────
def _norm_tag(s):
    """Очистка метки: убрать backticks/жирность/краевые пробелы."""
    t = (s or "").strip().strip("`").strip()
    t = t.replace("*", "")
    return re.sub(r"\s+", " ", t).strip()


def _parse_rank(s):
    """Ранг 0-3 из строки; None если не число."""
    m = re.search(r"\b([0-3])\b", s or "")
    if not m:
        return None
    return int(m.group(1))


def _extract_date(s):
    """Первая ISO-дата в строке -> date; None если нет."""
    m = _DATE_RE.search(s or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _split_links(s):
    """Список связей из ячейки «Связи» (через запятую/точку с запятой)."""
    out = []
    for part in re.split(r"[,;]", s or ""):
        p = _norm_tag(part)
        if p and p not in ("-", "—", "..."):
            out.append(p)
    return out


def _mk_node(tag, rank, links, status, source):
    return {
        "tag": tag,
        "rank": rank,
        "links": list(links),
        "status": (status or "").strip(),
        "updated": _extract_date(status),
        "source": source,
    }


def _has_reason(status):
    s = (status or "").lower()
    return any(m in s for m in _REASON_MARKERS)


def alert(code, tag, message):
    return {"code": code, "severity": SEVERITY[code], "tag": tag, "message": message}


# ── Парсеры ──────────────────────────────────────────────────────────────
def parse_claims_table(text):
    """Парсит markdown-таблицу графа (Тег/Ранг/Связи/Статус) + строки-метки.

    Возвращает list[Node]. Ловит строки формата [тег: X][ранг:1][связи: a, b].
    """
    nodes = []
    lines = text.splitlines()

    # 1) таблица графа: строка заголовка содержит Тег|Ранг|Связи
    header_idx = None
    for i, ln in enumerate(lines):
        if re.match(r"\s*\|", ln) and all(k in ln.lower()
                                          for k in ("тег", "ранг", "связи")):
            header_idx = i
            break
    if header_idx is not None:
        for ln in lines[header_idx + 1:]:
            if not re.match(r"\s*\|", ln):
                break  # конец таблицы
            body = ln.strip()
            if body.startswith("|") and body.endswith("|"):
                body = body[1:-1]
            cells = [c.strip() for c in body.split("|")]
            if len(cells) < 3:
                continue
            tag = _norm_tag(re.sub(r"`", "", cells[0]))
            if not tag or set(tag) <= {"-", ":", " ", "|"}:
                continue
            rank = _parse_rank(cells[1])
            if rank is None:
                continue  # разделитель / строка без ранга — не узел
            links = _split_links(cells[2])
            status = _norm_tag(cells[3]) if len(cells) > 3 else ""
            nodes.append(_mk_node(tag, rank, links, status, "claims_table"))

    # 2) строки-метки [тег: X][ранг:N][связи: ...] по всему тексту
    for m in _TAGLINE_RE.finditer(text):
        tag = _norm_tag(m.group(1))
        if not tag:
            continue
        seg = text[m.end(): m.end() + 200]
        rm = re.search(r"\[\s*ранг\s*:\s*([^\]]+?)\s*\]", seg)
        rank = _parse_rank(rm.group(1)) if rm else None
        if rank is None:
            continue  # пример/без ранга — не узел графа
        links = []
        lm = re.search(r"\[\s*связи\s*:\s*([^\]]+?)\s*\]", seg)
        if lm:
            links = _split_links(lm.group(1))
        nodes.append(_mk_node(tag, rank, links, "метка из сообщения", "tag_line"))

    return nodes


def parse_todo_file(path):
    """H1-H4/M1-M4/N1-N3/D1-D3/R1-R4/T1-T4 как узлы (ранг по умолчанию 3)."""
    text = Path(path).read_text(encoding="utf-8")
    nodes = []
    for ln in text.splitlines():
        m = _TODO_ID_RE.match(ln)
        if not m:
            continue
        tid = m.group(1)
        rm = re.search(r"\[\s*ранг\s*:\s*([0-3])\s*\]", ln)
        rank = int(rm.group(1)) if rm else 3
        lm = re.search(r"\[\s*связи\s*:\s*([^\]]+)\s*\]", ln)
        links = _split_links(lm.group(1)) if lm else []
        status = ln[m.end():].strip().split("—")[0][:80]
        nodes.append(_mk_node(tid, rank, links, status, "todo_file"))
    return nodes


def collect_known_tags(text):
    """Backtick-токены документа как «известные» теги/сущности."""
    out = set()
    for m in re.finditer(r"`([^`]+)`", text or ""):
        t = _norm_tag(m.group(1))
        if t and _TAGLIKE_RE.match(t) and " " not in t:
            out.add(t)
    return out


def _expand_id_ref(link):
    """N1-N3 -> [N1, N2, N3]; T8 -> [T8] при известном семействе."""
    m = re.fullmatch(r"([A-Z])(\d+)(?:-([A-Z])(\d+))?", link)
    if not m:
        return None
    fam, a, fam2, b = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    if fam2 and fam2 != fam:
        return None
    lo, hi = a, int(b) if b else a
    if lo > hi:
        return None
    if fam not in _ID_FAMILIES:
        return None
    return [f"{fam}{i}" for i in range(lo, hi + 1)]


def load_tracker(claims_path, todo_path=None):
    """Читает реальный трекер + опц. todo-лист; возвращает (graph, alerts).

    Парсер таблицы — строго по разделу «ГРАФ СВЯЗЕЙ ЗАДАЧ»; теги, задокумен-
    тированные в заметках/статусах (backtick-токены) и в todo-листе (H1-H4,
    M1-M4, N1-N3, D1-D3, R1-R4, T1-T4), расширяют словарь известных тегов:
    реальный трекер ссылается на сущности, которых нет в таблице — это
    легитимная навигация, а не битые связи.
    """
    claims_text = Path(claims_path).read_text(encoding="utf-8")
    nodes = parse_claims_table(claims_text)
    todo_nodes = []
    todo_text = ""
    if todo_path:
        todo_text = Path(todo_path).read_text(encoding="utf-8")
        todo_nodes = parse_todo_file(todo_path)
        nodes += todo_nodes
    g = build_graph(nodes)
    g.known_tags |= collect_known_tags(claims_text)
    if todo_text:
        g.known_tags |= collect_known_tags(todo_text)
        g.known_tags |= {n["tag"] for n in todo_nodes}
    alerts = validate_invariants(g)
    return g, alerts


def link_resolvable(link, known_tags):
    """Связь считается валидной (не битой)."""
    if link in WILDCARD_LINKS:
        return True
    if link in known_tags:
        return True
    if any(t.startswith(link) for t in known_tags):
        return True
    ids = _expand_id_ref(link)
    if ids:
        if any(i in known_tags for i in ids):
            return True
        m = re.fullmatch(r"([A-Z])\d+", link)
        if m and m.group(1) in _ID_FAMILIES:
            return True
        m2 = re.fullmatch(r"([A-Z])\d+-[A-Z]\d+", link)
        if m2 and m2.group(1) in _ID_FAMILIES:
            return True
    return False


def _resolve_link(link, known_tags):
    """Канонический тег-цель связи для рёбер графа; None если не узел."""
    if link in known_tags:
        return link
    hits = [t for t in known_tags if t.startswith(link)]
    if len(hits) == 1:
        return hits[0]
    if hits:
        return link  # неоднозначно, но реально; рёбра фильтруются по graph
    return None


# ── Граф ─────────────────────────────────────────────────────────────────
class Graph(dict):
    def __init__(self):
        super().__init__()
        self.order = []
        self.duplicates = []
        self.rank_conflicts = []
        self.known_tags = set()


def build_graph(nodes):
    """Граф: dict tag -> Node + метаданные для инвариантов I3/I4."""
    g = Graph()
    for n in nodes:
        if n["tag"] not in g:
            g[n["tag"]] = n
    g.order = list(g.keys())
    counts = Counter(n["tag"] for n in nodes)
    g.duplicates = sorted(t for t, c in counts.items() if c > 1)

    per = defaultdict(list)
    for n in nodes:
        per[n["tag"]].append(n)
    conflicts = []
    for tag, lst in per.items():
        tables = [n for n in lst if n["source"] == "claims_table"]
        others = [n for n in lst if n["source"] != "claims_table"]
        if not tables or not others:
            continue
        cur = tables[0]["rank"]
        declared = max((n["rank"] for n in others if n["rank"] is not None),
                       default=None)
        if (cur is not None and declared is not None and cur > declared
                and not _has_reason(tables[0]["status"])):
            conflicts.append((tag, declared, cur))
    g.rank_conflicts = conflicts
    g.known_tags = set(g.keys())
    return g


# ── Инварианты ───────────────────────────────────────────────────────────
def _dependency_edges(graph):
    """Исходящие рёбра только по реальным (не wildcard) ссылкам между узлами."""
    tags = list(graph.order)
    dep = {t: set() for t in tags}
    incoming = defaultdict(set)
    for t in tags:
        node = graph[t]
        for lnk in node["links"]:
            if lnk in WILDCARD_LINKS:
                continue
            res = _resolve_link(lnk, graph.known_tags)
            if res is None or res not in graph or res == t:
                continue
            dep[t].add(res)
            incoming[res].add(t)
    return dep, incoming


def _components(graph):
    """Компоненты связности (неориентированные), wildcard «все» = связи со всеми."""
    tags = list(graph.order)
    adj = defaultdict(set)
    for t in tags:
        for lnk in graph[t]["links"]:
            if lnk in WILDCARD_LINKS:
                for o in tags:
                    if o != t:
                        adj[t].add(o)
                continue
            res = _resolve_link(lnk, graph.known_tags)
            if res is None:
                continue
            if res in graph and res != t:
                adj[t].add(res)
                adj[res].add(t)
    comp = {}
    cid = 0
    for t in tags:
        if t in comp:
            continue
        stack = [t]
        comp[t] = cid
        while stack:
            v = stack.pop()
            for w in adj[v]:
                if w not in comp:
                    comp[w] = cid
                    stack.append(w)
        cid += 1
    return comp


def _sccs(dep, tags):
    """Сильно связные компоненты размера >1 (циклы), Tarjan."""
    index, low, onstack, stack, res, cnt = {}, {}, set(), [], [], [0]

    def sc(v):
        index[v] = low[v] = cnt[0]
        cnt[0] += 1
        stack.append(v)
        onstack.add(v)
        for w in dep[v]:
            if w not in index:
                sc(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                x = stack.pop()
                onstack.discard(x)
                comp.append(x)
                if x == v:
                    break
            if len(comp) > 1:
                res.append(sorted(comp))

    for t in tags:
        if t not in index:
            sc(t)
    return res


def validate_invariants(graph):
    """7 инвариантов -> list[Alert] (I1-I4, I6-I7; I5 — в detect_stale)."""
    tags = list(graph.order)
    dep, incoming = _dependency_edges(graph)
    alerts = []
    wildcard_sources = {t for t in tags
                        if any(l in WILDCARD_LINKS for l in graph[t]["links"])}

    # I1 — сирота ранга 1: нет ни одной связи (ни исходящей, ни входящей)
    for t in tags:
        node = graph[t]
        if node["rank"] != 1:
            continue
        if not node["links"] and not incoming.get(t) \
                and not any(o != t for o in wildcard_sources):
            alerts.append(alert(I1, t,
                                "активный узел ранга 1 без связей (сирота)"))

    # I2 — битые связи
    for t in tags:
        for lnk in graph[t]["links"]:
            if lnk in WILDCARD_LINKS:
                continue
            if not link_resolvable(lnk, graph.known_tags):
                alerts.append(alert(I2, t,
                                    f"связь на несуществующий тег: {lnk}"))

    # I3 — дубли тегов
    for t in graph.duplicates:
        alerts.append(alert(I3, t, "тег встречается более одного раза"))

    # I4 — деградация ранга без причины в статусе
    for t, declared, current in graph.rank_conflicts:
        alerts.append(alert(I4, t,
                            f"ранг {declared} → {current} без отметки причины "
                            f"в статусе"))

    # I6 — активная задача не связана с ранговым узлом 0
    comp = _components(graph)
    rank0 = [t for t in tags if graph[t]["rank"] == 0]
    rank1 = [t for t in tags if graph[t]["rank"] == 1]
    if rank0:
        root = comp[rank0[0]]
        for t in rank1:
            if comp[t] != root:
                alerts.append(alert(I6, t,
                                    f"активный узел не связан с ранговым узлом 0 "
                                    f"({rank0[0]})"))
    else:
        for t in rank1:
            alerts.append(alert(I6, t, "нет узлов ранга 0 — общий узел отсутствует"))

    # I7 — циклы зависимостей (по направленным рёбрам)
    for cyc in _sccs(dep, tags):
        alerts.append(alert(I7, cyc[0],
                            "цикл зависимостей: " + " -> ".join(cyc)))
    for t in tags:
        if t in dep.get(t, set()):
            alerts.append(alert(I7, t, "само-ссылка (цикл) на себя"))

    return alerts


def detect_stale(nodes, now, stale_days=DEFAULT_STALE_DAYS):
    """I5 — активные узлы без обновления > stale_days (по дате в статусе)."""
    alerts = []
    for n in nodes:
        if n.get("rank") != 1:
            continue
        up = n.get("updated")
        if up is None:
            continue  # нет даты — не можем детерминированно утверждать
        days = (now - up).days
        if days > stale_days:
            alerts.append(alert(I5, n["tag"],
                                f"активный узел не обновлялся {days} дней "
                                f"(лимит {stale_days})"))
    return alerts


def _topo_prio(t, graph):
    r = graph[t]["rank"]
    if r == 1:
        return (0, 0, t)
    return (1, r if r is not None else 3, t)


def topological_order(graph):
    """Топосорт (Kahn) с приоритетом ранга 1; узлы циклов — в конец списка."""
    tags = list(graph.order)
    dep, _ = _dependency_edges(graph)
    indeg = {t: 0 for t in tags}
    for outs in dep.values():
        for w in outs:
            indeg[w] += 1
    ready = [t for t in tags if indeg[t] == 0]

    ordered = []
    while ready:
        ready.sort(key=lambda t: _topo_prio(t, graph))
        t = ready.pop(0)
        ordered.append(t)
        for w in sorted(dep[t]):
            indeg[w] -= 1
            if indeg[w] == 0:
                ready.append(w)
    rest = [t for t in tags if t not in ordered]
    rest.sort(key=lambda t: _topo_prio(t, graph))
    ordered.extend(rest)
    return [graph[t] for t in ordered]


# ── Отчёт ────────────────────────────────────────────────────────────────
def format_report(alerts, order, graph=None, stale_days=DEFAULT_STALE_DAYS):
    """Markdown-отчёт: инварианты, алерты, порядок выполнения."""
    lines = ["# Отчёт контроля техдолга (techdebt_control.py)", ""]
    if graph is not None:
        lines.append(f"**Узлов в графе:** {len(graph)}")
        crit = sum(1 for a in alerts if a["severity"] == "CRITICAL")
        warn = sum(1 for a in alerts if a["severity"] == "WARNING")
        lines.append(f"**Алерты:** {crit} CRITICAL, {warn} WARNING")
        lines.append(f"**Stale-лимит:** {stale_days} дней")
        lines.append("")

    codes = {a["code"] for a in alerts}
    lines.append("## Инварианты")
    lines.append("| Инвариант | Статус |")
    lines.append("|---|---|")
    for code in (I1, I2, I3, I4, I5, I6, I7):
        lines.append(f"| {INVARIANT_NAMES[code]} | "
                     f"{'FAIL' if code in codes else 'OK'} |")

    lines.append("")
    lines.append("## Алерты")
    if not alerts:
        lines.append("_чисто_")
    else:
        lines.append("| Код | Severity | Тег | Сообщение |")
        lines.append("|---|---|---|---|")
        for a in sorted(alerts, key=lambda a: (a["severity"] != "CRITICAL",
                                               a["code"], a["tag"])):
            lines.append(f"| {a['code']} | {a['severity']} | `{a['tag']}` | "
                         f"{a['message']} |")

    lines.append("")
    lines.append("## Порядок выполнения (топосорт)")
    if not order:
        lines.append("_пусто_")
    else:
        for i, n in enumerate(order, 1):
            lines.append(f"{i}. `{n['tag']}` (ранг {n['rank']})")
    lines.append("")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────
def _node_to_dict(n):
    return {
        "tag": n["tag"],
        "rank": n["rank"],
        "links": list(n["links"]),
        "status": n["status"],
        "updated": n["updated"].isoformat() if n["updated"] else None,
        "source": n["source"],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="techdebt_control.py",
        description="Контроль техдолга оркестратора по графу задач (слои 0-3).")
    ap.add_argument("--claims", required=True,
                    help="путь к RESEARCHER_CLAIMS.md (раздел «ГРАФ СВЯЗЕЙ ЗАДАЧ»)")
    ap.add_argument("--todo", default=None,
                    help="опц. путь к resercher-todo.md (H1-H4/M1-M4/... как узлы)")
    ap.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS,
                    help="лимит дней без обновления активной задачи")
    ap.add_argument("--json", action="store_true", help="выход JSON в stdout")
    ap.add_argument("--report", default=None, help="записать markdown-отчёт в файл")
    args = ap.parse_args(argv)

    try:
        todo_text = Path(args.todo).read_text(encoding="utf-8") if args.todo else ""
        todo_nodes = parse_todo_file(args.todo) if args.todo else []
    except OSError as e:
        print(f"ERROR: не удалось прочитать {args.todo}: {e}", file=sys.stderr)
        return 2

    try:
        g, alerts = load_tracker(args.claims, args.todo)
    except OSError as e:
        print(f"ERROR: не удалось прочитать {args.claims}: {e}", file=sys.stderr)
        return 2

    alerts += detect_stale(list(g.values()), date.today(), args.stale_days)
    order = topological_order(g)

    result = {
        "nodes": [_node_to_dict(n) for n in g.values()],
        "alerts": alerts,
        "order": [n["tag"] for n in order],
        "cycles": [a["message"] for a in alerts if a["code"] == I7],
        "clean": not alerts,
        "summary": {
            "nodes": len(g),
            "critical": sum(1 for a in alerts if a["severity"] == "CRITICAL"),
            "warning": sum(1 for a in alerts if a["severity"] == "WARNING"),
        },
        "stale_days": args.stale_days,
        "sources": {"claims": args.claims, "todo": args.todo},
    }
    out = json.dumps(result, ensure_ascii=False, indent=2)

    if args.json:
        print(out)
    else:
        print(f"Узлов: {len(g)}; CRITICAL: {result['summary']['critical']}, "
              f"WARNING: {result['summary']['warning']}")

    if args.report:
        Path(args.report).write_text(
            format_report(alerts, order, g, args.stale_days),
            encoding="utf-8")

    # артефакт по конвенции content_verdict_results.json
    try:
        Path("techdebt_control_results.json").write_text(out, encoding="utf-8")
    except OSError:
        pass

    return 0 if not alerts else 1


if __name__ == "__main__":
    sys.exit(main())
