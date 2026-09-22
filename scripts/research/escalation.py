#!/usr/bin/env python3
"""escalation.py — Волна 4, резак и ленивые рёбра (слой 7.5).

Зародыш = AMBIGUOUS/UNSUPPORTED/OPEN группа.
Расширение +1 хоп: соседние группы в том же узле дерева направлений
(topics_tree.json) и в родительском узле.
Сходимость: >=2 независимых вердикта, conf>=0.8, dispersion<=0.2.
Превышение лимитов (max_hops/max_nodes/max_tokens) → OPEN + аларм.

Usage: python3 escalation.py <verdicts_processed.json> <topics_tree.json> <rules.yaml> <out.json>
"""
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from statistics import pstdev
from pathlib import Path


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_group_node(node, gid):
    if str(gid) in node.get("claims", []):
        return node
    for c in node.get("children", []):
        r = find_group_node(c, gid)
        if r:
            return r
    return None


def walk_nodes(node, acc):
    acc[node["id"]] = node
    for c in node.get("children", []):
        walk_nodes(c, acc)


def neighbors(verdicts, nodes, gid, node=None):
    """Ленивые рёбра: группы в том же узле и в родителе.

    node — уже найденный узел группы (find_group_node), иначе ищется по nodes.
    """
    if node is None:
        for n in nodes.values():
            if str(gid) in n.get("claims", []):
                node = n
                break
    if node is None:
        return []
    nbrs = [str(x) for x in node.get("claims", []) if str(x) != str(gid)]
    par = node.get("parent")
    if par and par in nodes:
        nbrs.extend(str(x) for x in nodes[par].get("claims", []))
    return list(dict.fromkeys(nbrs))


def converges(seen_verdicts, conv_min=2, conv_conf=0.8, conv_disp=0.2):
    """Сходимость: >=conv_min независимых подтверждающих вердиктов (зародыш не
    считается), conf каждого поддерживающего >= conv_conf, dispersion <= conv_disp.

    Контракт: `len(supporters)>=conv_min and pstdev(confs)<=conv_disp
    and min(conf)>=conv_conf` (min гарантирован фильтром supporters).
    """
    if len(seen_verdicts) < 2:
        return False
    supporters = [x for x in seen_verdicts[1:]
                  if x.get("verdict") == "SUPPORTED"
                  and x.get("confidence", 0.0) >= conv_conf]
    if len(supporters) < conv_min:
        return False
    confs = [s.get("confidence", 0.0) for s in supporters]
    if min(confs) < conv_conf:
        return False
    if pstdev(confs) > conv_disp:
        return False
    return True


def group_id(g):
    """Идентификатор группы: original_index (если есть), иначе claim_id (fallback)."""
    v = g.get("original_index")
    if v is None:
        v = g.get("claim_id")
    return v


def _to_int_or_str(v):
    """Безопасное приведение к int: 'None'/строки без int → возвращаются как str."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 escalation.py <verdicts.json> <topics_tree.json> <rules.yaml> <out.json>",
              file=sys.stderr)
        sys.exit(1)
    verdicts_path, topics_path, rules_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    verdicts = json.load(open(verdicts_path, encoding="utf-8"))
    if isinstance(verdicts, dict) and "verdicts" in verdicts:
        verdicts = verdicts["verdicts"]
    topics = json.load(open(topics_path, encoding="utf-8"))
    rules = load_yaml(rules_path)

    er = rules.get("escalation_rules", {})
    seeds = set(er.get("seeds", ["AMBIGUOUS", "UNSUPPORTED", "OPEN"]))
    max_hops = er.get("max_hops", 3)
    max_nodes = er.get("max_nodes", 15)
    max_tokens = er.get("max_tokens", 40000)
    conv = er.get("convergence", {})
    conv_min = conv.get("min_verdicts", 2)
    conv_conf = conv.get("min_confidence", 0.8)
    conv_disp = conv.get("max_dispersion", 0.2)

    by_id = {}
    for g in verdicts:
        # Два ID-пространства (claim_id vs original_index): индекс по обоим.
        oi = g.get("original_index")
        if oi is not None:
            by_id.setdefault(str(oi), g)
        ci = g.get("claim_id")
        if ci is not None:
            by_id.setdefault(str(ci), g)
    nodes = {}
    walk_nodes(topics["topics_tree"], nodes)

    n_converged = 0
    n_open = 0
    alarms = []
    processed = set()
    hops_used = 0

    for g in verdicts:
        if g.get("verdict") not in seeds:
            continue
        gid = group_id(g)
        if gid is None:
            # группа без идентификатора — эскалировать нечего, не падаем
            print(f"⚠ escalation: вердикт без original_index и claim_id — пропущен")
            continue
        gid = str(gid)
        if gid in processed:
            continue
        processed.add(gid)

        # расширение +1 хоп: узел группы через find_group_node, рёбра через neighbors
        seen = [g]
        seed_node = find_group_node(topics["topics_tree"], gid)
        frontier = neighbors(verdicts, nodes, gid, seed_node)
        hops = 0
        while frontier and hops < max_hops and len(seen) < max_nodes:
            nxt = []
            for nid in frontier:
                if nid not in by_id:
                    continue
                ng = by_id[nid]
                if ng in seen:
                    continue
                seen.append(ng)
                nxt.extend(neighbors(verdicts, nodes, nid,
                                     find_group_node(topics["topics_tree"], nid)))
            frontier = list(dict.fromkeys(nxt))[: max_nodes - len(seen)]
            hops += 1
        hops_used += hops

        tokens_est = sum(len(x.get("claims", [])) for x in seen) * 100
        confs = [x.get("confidence", 0.0) for x in seen]
        ok = tokens_est <= max_tokens and converges(seen, conv_min, conv_conf, conv_disp)

        if ok:
            n_converged += 1
            g["escalation"] = {
                "status": "LOCAL",
                "scope": "local",
                "hops": hops,
                "n_evidence": len(seen),
                "confidence": min(confs),
            }
        else:
            n_open += 1
            g["escalation"] = {
                "status": "OPEN",
                "scope": "open",
                "hops": hops,
                "n_evidence": len(seen),
                "confidence": min(confs) if confs else 0.0,
            }
            g["verdict"] = "OPEN"
            alarm = {
                "type": er.get("cut_off", {}).get("alarm_type", "escalation_cutoff"),
                "group": _to_int_or_str(gid),
                "detail": f"не сходится за {hops} хопов, вердиктов {len(seen)}, "
                          f"conf {min(confs) if confs else 0:.2f}",
                "hops": hops,
            }
            g["_alarm"] = alarm
            alarms.append(alarm)

    summary = {
        "seeds": list(seeds),
        "n_seeds": len(processed),
        "n_converged": n_converged,
        "n_open": n_open,
        "hops_used": hops_used,
        "alarms": alarms,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"verdicts": verdicts, "summary": summary}, f,
                  ensure_ascii=False, indent=1)
    print(f"✅ escalation: зародышей {len(processed)}, сходится {n_converged}, "
          f"OPEN {n_open}, алармов {len(alarms)}, хопов {hops_used}")


if __name__ == "__main__":
    main()
