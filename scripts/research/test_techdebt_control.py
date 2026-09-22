#!/usr/bin/env python3
"""test_techdebt_control.py — реальные (не мок) тесты контроля техдолга.

Покрывает чекпоинты задания (план §3.8, 12 тестов):
  1.  парсинг реальной таблицы RESEARCHER_CLAIMS.md;
  2.  тег-синтаксис [тег: X][ранг:N][связи: a, b];
  3-9. семь инвариантов I1-I7 (микро-данные, быстрые);
  10.  топосорт на DAG;
  11.  test_real_claims_clean — ключевой: реальный трекер без false-positive
      CRITICAL;
  12.  CLI --json + exit code (реальный запуск подпроцессом).

Никаких моков: парсер всегда читает реальный файл трекера с диска.
"""
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import techdebt_control as tc

# ── Реальный источник истины ────────────────────────────────────────────
TRACKER = Path("/home/orangepi/Документы/doc_hermes_pi/RESEARCHER_CLAIMS.md")
REQUIRE_TRACKER = TRACKER.exists()


def _table_text():
    assert REQUIRE_TRACKER, f"реальный трекер недоступен: {TRACKER}"
    return TRACKER.read_text(encoding="utf-8")


def _p(name, rank, links, status="", source="claims_table"):
    return tc._mk_node(name, rank, links, status, source)


def _g(nodes):
    return tc.build_graph(nodes)


# ── 1. Парсер реальной таблицы ──────────────────────────────────────────
@pytest.mark.skipif(not REQUIRE_TRACKER, reason="реальный трекер недоступен")
def test_parse_claims_table():
    nodes = tc.parse_claims_table(_table_text())
    table_nodes = [n for n in nodes if n["source"] == "claims_table"]
    assert len(table_nodes) >= 12, \
        f"реальная таблица графа должна дать >=12 узлов, получено {len(table_nodes)}"
    tags = {n["tag"] for n in table_nodes}
    # ключевые узлы реального графа обязаны быть
    for must in ("оркестрация-задач", "задача1-починка", "числовой-слой",
                 "тег-автоматизация", "контроль-техдолга"):
        assert must in tags, f"в реальном графе нет узла {must}"
    rank0 = {n["tag"] for n in table_nodes if n["rank"] == 0}
    rank1 = {n["tag"] for n in table_nodes if n["rank"] == 1}
    rank2 = {n["tag"] for n in table_nodes if n["rank"] == 2}
    assert rank0 == {"оркестрация-задач"}, f"ранг 0: {rank0}"
    assert len(rank1) >= 4, f"ранг 1: {rank1}"
    assert "оркестрация" in {tuple(n["links"]) for n in table_nodes
                             if n["tag"] == "deliberation"}.pop()
    assert "все" in {tuple(n["links"]) for n in table_nodes
                     if n["tag"] == "оркестрация-задач"}.pop()
    assert all(0 <= n["rank"] <= 3 for n in table_nodes), \
        "все ранги реальной таблицы в слоях 0-3"


# ── 2. Тег-синтаксис ────────────────────────────────────────────────────
def test_parse_tag_syntax():
    line = "Сообщение: [тег: X][ранг:1][связи: a, b] для оркестратора"
    nodes = tc.parse_claims_table(line)
    tag_nodes = [n for n in nodes if n["source"] == "tag_line"]
    assert len(tag_nodes) == 1
    n = tag_nodes[0]
    assert n["tag"] == "X"
    assert n["rank"] == 1
    assert n["links"] == ["a", "b"]


def test_parse_tag_syntax_spaces_and_cyrillic():
    line = ("[тег: активная-задача][ранг: 1][связи: база-знаний, "
            "тезис2-актуальность]")
    nodes = tc.parse_claims_table(line)
    tag_nodes = [n for n in nodes if n["source"] == "tag_line"]
    assert len(tag_nodes) == 1
    n = tag_nodes[0]
    assert n["tag"] == "активная-задача"
    assert n["rank"] == 1
    assert set(n["links"]) == {"база-знаний", "тезис2-актуальность"}


# ── Инварианты I1-I7 ────────────────────────────────────────────────────
def test_i1_orphan_rank1():
    nodes = [
        _p("active-orphan", 1, [], "todo"),
        _p("ok-active", 1, ["data"]),
        _p("data", 2, [], "готово"),
    ]
    alerts = tc.validate_invariants(_g(nodes))
    i1 = [a for a in alerts if a["code"] == tc.I1]
    assert len(i1) == 1
    assert i1[0]["tag"] == "active-orphan"
    assert i1[0]["severity"] == "CRITICAL"


def test_i2_broken_link():
    nodes = [
        _p("active", 1, ["ghost-tag", "ok"]),
        _p("ok", 2, []),
    ]
    alerts = tc.validate_invariants(_g(nodes))
    i2 = [a for a in alerts if a["code"] == tc.I2]
    assert len(i2) == 1
    assert i2[0]["tag"] == "active"
    assert "ghost-tag" in i2[0]["message"]
    assert i2[0]["severity"] == "CRITICAL"


def test_i3_duplicate_tag():
    nodes = [
        _p("dup", 2, [], "a"),
        _p("dup", 2, [], "b"),
        _p("root", 0, ["dup"]),
    ]
    g = _g(nodes)
    alerts = tc.validate_invariants(g)
    i3 = [a for a in alerts if a["code"] == tc.I3]
    assert len(i3) == 1
    assert i3[0]["tag"] == "dup"
    assert i3[0]["severity"] == "WARNING"


def test_i4_rank_degrade():
    # текущий ранг в таблице 3, объявленный (метка) был 1 — деградация без причины
    nodes = [
        _p("t", 3, ["root"], "C1-C4 закрыты"),
        _p("t", 1, [], "метка: [ранг:1]", "tag_line"),
        _p("root", 0, ["t"]),
    ]
    g = _g(nodes)
    assert len(g.rank_conflicts) == 1
    assert g.rank_conflicts[0][1:] == (1, 3)  # declared=1, current=3
    alerts = tc.validate_invariants(g)
    i4 = [a for a in alerts if a["code"] == tc.I4]
    assert len(i4) == 1
    assert i4[0]["severity"] == "WARNING"


def test_i4_no_false_positive_with_reason():
    # деградация С ПОМЕТКОЙ причины (explicit "понижен") — алерта быть не должно
    nodes = [
        _p("t", 3, ["root"], "деградация: понижен до 3, см. анализ"),
        _p("t", 1, [], "метка: [ранг:1]", "tag_line"),
        _p("root", 0, ["t"]),
    ]
    g = _g(nodes)
    assert len(g.rank_conflicts) == 0, "с пометкой причины конфликт не фиксируется"
    alerts = tc.validate_invariants(g)
    assert not [a for a in alerts if a["code"] == tc.I4]


def test_i5_stale():
    old = (date.today() - timedelta(days=20)).isoformat()
    fresh = (date.today() - timedelta(days=2)).isoformat()
    nodes = [
        _p("old", 1, ["data"], f"TODO {old}"),
        _p("new", 1, ["data"], f"todo {fresh}"),
        _p("data", 2, [], "готово"),
    ]
    alerts = tc.detect_stale(nodes, date.today(), stale_days=14)
    i5 = [a for a in alerts if a["code"] == tc.I5]
    assert [a["tag"] for a in i5] == ["old"]
    assert "20 дней" in i5[0]["message"]


def test_i5_ignores_future_and_no_date():
    fut = (date.today() + timedelta(days=5)).isoformat()
    nodes = [
        _p("future", 1, ["data"], f"todo {fut}"),
        _p("nodate", 1, ["data"], "todo без даты"),
    ]
    alerts = tc.detect_stale(nodes, date.today(), stale_days=14)
    assert not [a for a in alerts if a["code"] == tc.I5]


def test_i6_connectivity():
    nodes = [
        _p("root", 0, ["x"]),
        _p("lost", 1, ["ghost"]),
        _p("ok", 1, ["x"]),
        _p("x", 2, [], "готово"),
    ]
    g = _g(nodes)
    alerts = tc.validate_invariants(g)
    i6 = [a for a in alerts if a["code"] == tc.I6]
    assert [a["tag"] for a in i6] == ["lost"]
    assert i6[0]["severity"] == "CRITICAL"


def test_i6_with_wildcard_connected():
    # узел со связью «все» соединён со всеми — сирот/разрыва нет
    nodes = [
        _p("root", 0, ["все"]),
        _p("a1", 1, []),
        _p("a2", 1, []),
    ]
    g = _g(nodes)
    alerts = tc.validate_invariants(g)
    assert not [a for a in alerts if a["code"] == tc.I6]
    assert not [a for a in alerts if a["code"] == tc.I1]


def test_i7_cycle():
    nodes = [
        _p("a", 2, ["b"]),
        _p("b", 2, ["c"]),
        _p("c", 2, ["a"]),
    ]
    g = _g(nodes)
    alerts = tc.validate_invariants(g)
    i7 = [a for a in alerts if a["code"] == tc.I7]
    assert len(i7) == 1
    assert i7[0]["severity"] == "WARNING"
    assert "a" in i7[0]["message"] and "b" in i7[0]["message"]


def test_i7_no_cycle_on_dag():
    nodes = [
        _p("a", 2, ["b"]),
        _p("b", 2, ["c"]),
        _p("c", 2, []),
    ]
    alerts = tc.validate_invariants(_g(nodes))
    assert not [a for a in alerts if a["code"] == tc.I7]


# ── 10. Топосорт ────────────────────────────────────────────────────────
def test_topological_order():
    nodes = [
        _p("root", 0, ["a1", "a2", "s1"]),
        _p("s1", 2, ["s2"]),       # s1 блокирует s2
        _p("s2", 3, []),
        _p("a1", 1, ["s1"]),       # активная зависит от s1
        _p("a2", 1, ["s1", "s2"]),
    ]
    order = tc.topological_order(_g(nodes))
    tags = [n["tag"] for n in order]
    assert tags[0] == "root", f"ранг 0 впереди: {tags}"
    assert tags.index("a1") < tags.index("s1"), \
        f"активные раньше блокируемых: {tags}"
    assert tags.index("s1") < tags.index("s2"), \
        f"блокирующее раньше блокируемого: {tags}"
    assert set(tags) == {"root", "s1", "s2", "a1", "a2"}


def test_topological_order_cycles_appended():
    nodes = [
        _p("a", 2, ["b"]),
        _p("b", 2, ["c"]),
        _p("c", 2, ["a"]),
        _p("z", 3, []),
    ]
    order = tc.topological_order(_g(nodes))
    tags = [n["tag"] for n in order]
    assert tags[0] == "z", f"нециклический узел впереди: {tags}"
    assert set(tags[1:]) == {"a", "b", "c"}


# ── 11. КЛЮЧЕВОЙ: реальный трекер без false-positive CRITICAL ───────────
@pytest.mark.skipif(not REQUIRE_TRACKER, reason="реальный трекер недоступен")
def test_real_claims_clean():
    g, alerts = tc.load_tracker(str(TRACKER))
    assert len(g) >= 12, "реальная таблица не распарсилась вообще"
    order = tc.topological_order(g)
    crit = [a for a in alerts if a["severity"] == "CRITICAL"]
    # главный критерий: НИ ОДНОГО ложного CRITICAL на реальном трекере
    assert not crit, f"false-positive CRITICAL на реальном трекере: {crit}"
    # стабильность: каждый реальный узел есть в топосорте ровно один раз
    assert len(order) == len(g)
    assert {n["tag"] for n in order} == set(g.keys())
    # I6 не должен сработать: реальный граф связен через оркестрацию-задач
    i6 = [a for a in alerts if a["code"] == tc.I6]
    assert not i6, f"связность реального графа нарушена: {i6}"


# ── 12. CLI --json + exit code (реальный запуск) ────────────────────────
@pytest.mark.skipif(not REQUIRE_TRACKER, reason="реальный трекер недоступен")
def test_cli_json(tmp_path):
    res = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "techdebt_control.py"),
         "--claims", str(TRACKER), "--json",
         "--report", str(tmp_path / "report.md")],
        capture_output=True, text=True, timeout=120)
    assert res.returncode in (0, 1), f"CLI упал: {res.stderr}"
    data = json.loads(res.stdout)
    assert "nodes" in data and "alerts" in data and "order" in data
    assert isinstance(data["nodes"], list) and len(data["nodes"]) >= 12
    assert all(n["tag"] for n in data["nodes"])
    for a in data["alerts"]:
        assert a["code"] in (tc.I1, tc.I2, tc.I3, tc.I4, tc.I5, tc.I6, tc.I7)
        assert a["severity"] in ("CRITICAL", "WARNING")
    assert set(data["order"]) == {n["tag"] for n in data["nodes"]}
    crit = data["summary"]["critical"]
    # на реальном трекере не должно быть CRITICAL вообще (тест 11)
    assert crit == 0, f"CLI выдал CRITICAL на реальном трекере: {data['alerts']}"
    # отчёт-файл создан и содержит секции
    rep = (tmp_path / "report.md").read_text(encoding="utf-8")
    for sec in ("Инварианты", "Алерты", "Порядок выполнения"):
        assert sec in rep, f"в отчёте нет секции {sec}"


def test_cli_missing_file_exit_2():
    res = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "techdebt_control.py"),
         "--claims", "/nonexistent/claims.md", "--json"],
        capture_output=True, text=True, timeout=60)
    assert res.returncode == 2


def test_cli_clean_dag_exit_0(tmp_path):
    tracker = tmp_path / "fake.md"
    tracker.write_text(
        "| Тег | Ранг | Связи | Статус |\n"
        "|---|---|---|---|\n"
        "| `root` | 0 | все | активен |\n"
        "| `a1` | 1 | root | в работе |\n",
        encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "techdebt_control.py"),
         "--claims", str(tracker), "--json"],
        capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"чистый DAG должен вернуть 0: {res.stdout}"
    assert json.loads(res.stdout)["clean"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
