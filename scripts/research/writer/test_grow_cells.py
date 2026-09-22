#!/usr/bin/env python3
"""Тесты роста по графу (T2): neighbors, in_competence, _grow_cells, plan_patches+tree."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from sexpr import SExpr
from patch_planner import (
    plan_patches, _grow_cells, neighbors, in_competence, _build_nodes,
)

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("  FAIL: " + msg)


TOPICS_TREE = {
    "topics_tree": {
        "id": "root",
        "claims": [1, 2],
        "children": [
            {"id": "child1", "claims": [3, 4]},
            {"id": "child2", "claims": [8, 9],
             "children": [{"id": "grand", "claims": [7]}]},
        ],
    }
}


def v(gid, verdict, conf, problematic):
    return {
        "claim_id": gid,
        "claim_text": "claim " + str(gid),
        "verdict": verdict,
        "confidence": conf,
        "caveats": [],
        "problematic": problematic,
    }


VERDICTS = [
    v(1, "AMBIGUOUS", 0.6, True),
    v(2, "SUPPORTED", 0.95, False),
    v(3, "CONTRADICTED", 0.2, True),
    v(4, "SUPPORTED", 0.9, False),
    v(7, "AMBIGUOUS", 0.55, True),
    v(8, "CONTRADICTED", 0.3, True),
    v(9, "AMBIGUOUS", 0.6, True),
]


def groups_of(cell):
    out = []
    for p in cell.args:
        if isinstance(p, SExpr) and p.head == "patch":
            out.append(p["group"].args[0])
    return out


def test_build_nodes():
    nodes = _build_nodes(TOPICS_TREE)
    check(set(nodes.keys()) == {"root", "child1", "child2", "grand"}, "all nodes")
    check(nodes["child1"]["parent"] == "root", "child1 parent root")
    check(nodes["grand"]["parent"] == "child2", "grand parent child2")
    check(nodes["root"]["parent"] is None, "root has no parent")
    print("  test_build_nodes: OK")


def test_neighbors():
    nodes = _build_nodes(TOPICS_TREE)
    n = lambda g: [int(x) for x in neighbors(None, nodes, g)]
    check(n(3) == [4, 1, 2], "neighbors(3) = [4,1,2] (same node + parent)")
    check(n(1) == [2], "neighbors(1) = [2]")
    check(n(7) == [8, 9], "neighbors(7) = [8,9] (parent node)")
    check(n(8) == [9, 1, 2], "neighbors(8) = [9,1,2] (same + parent)")
    check(len(n(3)) == len(set(n(3))), "no duplicates in neighbors")
    print("  test_neighbors: OK")


def test_in_competence():
    check(in_competence(8, {"grand"}, TOPICS_TREE), "8 (parent node of seed) in competence")
    check(in_competence(4, {"child1"}, TOPICS_TREE), "4 in its own node scope")
    check(in_competence(7, {"child2"}, TOPICS_TREE), "7 (child node) in competence")
    check(in_competence(3, {"root"}, TOPICS_TREE), "3 (child of scope node) in competence")
    check(not in_competence(999, {"child1"}, TOPICS_TREE), "unknown group not in competence")
    check(not in_competence(3, set(), TOPICS_TREE), "empty scope -> not in competence")
    print("  test_in_competence: OK")


def test_grow_cells_no_tree():
    patches = plan_patches(VERDICTS)["patches"]
    cells = _grow_cells(patches, {})
    check(len(cells) == len(patches), "no tree -> 1 patch per cell")
    print("  test_grow_cells_no_tree: OK")


def test_grow_cells_graph():
    patches = plan_patches(VERDICTS)["patches"]
    cells = _grow_cells(patches, TOPICS_TREE, max_hops=3, max_nodes=15)

    total_groups = [g for c in cells for g in groups_of(c)]
    check(len(total_groups) == len(set(total_groups)), "no group duplicated across cells")

    cell_by_seed = {}
    for c in cells:
        gs = groups_of(c)
        cell_by_seed[gs[0]] = gs

    check(cell_by_seed[1] == [1], "seed 1 alone (only supported neighbor)")
    check(cell_by_seed[3] == [3], "seed 3 alone (neighbor 4 not problematic)")
    check(cell_by_seed[7] == [7, 8, 9], "seed 7 captures problematic neighbors 8,9")
    check(len(cells) == 3, "3 cells")
    print("  test_grow_cells_graph: OK")


def test_grow_cells_max_nodes():
    patches = plan_patches(VERDICTS)["patches"]
    cells = _grow_cells(patches, TOPICS_TREE, max_hops=1, max_nodes=1)
    check(all(len(groups_of(c)) == 1 for c in cells), "max_nodes=1 -> no capture")
    check(len(cells) == len(patches), "max_nodes=1 -> cells == patches")
    print("  test_grow_cells_max_nodes: OK")


def test_plan_patches_with_tree():
    plan = plan_patches(VERDICTS, {}, {}, TOPICS_TREE)
    check(plan["patch_count"] == 5, "5 patches (only problematic groups)")
    check(plan["cell_count"] == 3, "3 cells via graph growth")
    check(all(c.head == "cell" for c in plan["cells"]), "cells are (cell ...)")
    print("  test_plan_patches_with_tree: OK")


if __name__ == "__main__":
    print("=== test_grow_cells ===")
    test_build_nodes()
    test_neighbors()
    test_in_competence()
    test_grow_cells_no_tree()
    test_grow_cells_graph()
    test_grow_cells_max_nodes()
    test_plan_patches_with_tree()
    print("=== results: %d passed, %d failed ===" % (passed, failed))
    sys.exit(0 if failed == 0 else 1)
