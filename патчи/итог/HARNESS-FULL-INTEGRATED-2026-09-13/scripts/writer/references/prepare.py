#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any
from scripts.writer.references.graph_profile import digest as graph_digest
from scripts.writer.references.language import detect_fragments

SCHEMA = "reference_bundle/1.0"
ROLES = {"style", "evidence", "both"}

HEADING_RX = re.compile(r"^\s*(?:\d+(?:\.\d+){0,4}\s+)?([A-ZА-ЯЁ][^\n]{2,120}|Introduction|Experimental|Results(?: and discussion)?|Discussion|Conclusions?|Summary|References|ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|ВЫВОДЫ|МЕТОДЫ|РЕЗУЛЬТАТЫ)\s*$", re.I)
CITE_RX = re.compile(r"(?:\[[0-9,\-– ]+\]|\([A-ZА-ЯЁ][A-Za-zА-Яа-яЁё-]+\s+et\s+al\.,?\s*\d{4}\))")
HEDGE_RX = re.compile(r"\b(?:may|might|can|could|suggests?|approximately|about|likely|possible|вероятно|возможно|примерно|около|может|предположительно)\b", re.I)
CAUSAL_RX = re.compile(r"\b(?:because|therefore|thus|hence|leads? to|results? in|causes?|consequently|поскольку|поэтому|приводит к|обусловлен|вследствие)\b", re.I)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "document_inspection.v1" or not data.get("ok"):
        raise ValueError("reference.prepare requires successful document_inspection.v1")
    return data


def _lang(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if cyr > lat * 1.3: return "ru"
    if lat > cyr * 1.3: return "en_or_de"
    return "mixed"


def _kind(text: str) -> tuple[str, float, list[str]]:
    t = text[:25000]
    reasons=[]
    thesis = [r"\bdissertation\b", r"\bthesis\b", r"диссертац", r"доктор", r"кандидат", r"Ph\.?D", r"Dr\.-Ing", r"genehmigte\s+Abhandlung", r"zur\s+Erlangung"]
    article = [r"\babstract\b", r"\bkeywords\b", r"doi\s*:", r"Vols?\.", r"journal", r"©\s*\(?20\d{2}"]
    ts=sum(bool(re.search(x,t,re.I)) for x in thesis)
    ar=sum(bool(re.search(x,t,re.I)) for x in article)
    if ts>=2:
        reasons.append(f"thesis_signals:{ts}"); return "dissertation", min(.99,.65+.07*ts), reasons
    if ar>=3:
        reasons.append(f"article_signals:{ar}"); return "article", min(.97,.60+.07*ar), reasons
    return "unknown", .35, [f"thesis_signals:{ts}",f"article_signals:{ar}"]


def prepare(inspection: dict[str, Any], role: str, reference_id: str | None=None, graph_artifact: dict[str,Any] | None=None) -> dict[str, Any]:
    if role not in ROLES: raise ValueError(f"role must be one of {sorted(ROLES)}")
    segs=inspection.get("segments") or []
    pages=[str(s.get("text") or "") for s in segs]
    text="\n".join(pages)
    headings=[]
    for s in segs:
        loc=s.get("locator")
        for ln in str(s.get("text") or "").splitlines():
            x=" ".join(ln.split())
            if 3 <= len(x) <= 130 and HEADING_RX.match(x):
                headings.append({"text":x,"locator":loc})
                if len(headings)>=80: break
        if len(headings)>=80: break
    paras=[p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip())>=80]
    word_counts=[len(re.findall(r"\w+",p,re.U)) for p in paras]
    total_words=max(1,len(re.findall(r"\w+",text,re.U)))
    kind,kind_conf,kind_reasons=_kind(text)
    source_sha=inspection.get("sha256") or ""
    rid=reference_id or "REF-"+hashlib.sha256((source_sha+role).encode()).hexdigest()[:12]
    permissions={
        "style": {"style":True,"structure":True,"evidence":False,"claims":False},
        "evidence": {"style":False,"structure":False,"evidence":True,"claims":True},
        "both": {"style":True,"structure":True,"evidence":True,"claims":True},
    }[role]
    return {
      "ok":True,"schema":SCHEMA,"reference_id":rid,"role":role,
      "source":{"source_id":rid,"path":inspection.get("path"),"sha256":source_sha,"kind":inspection.get("kind"),"page_count":inspection.get("page_count")},
      "permissions":permissions,
      "profile":{
        "document_kind":kind,"kind_confidence":round(kind_conf,3),"kind_reasons":kind_reasons,
        "language":detect_fragments(pages[:12]).get("language",_lang(text)),"language_profile":detect_fragments(pages[:12]),"heading_count":len(headings),"headings":headings[:40],
        "sample_word_count":total_words,"paragraph_count":len(paras),
        "median_paragraph_words": sorted(word_counts)[len(word_counts)//2] if word_counts else 0,
        "citation_density_per_1000_words":round(1000*len(CITE_RX.findall(text))/total_words,3),
        "hedge_density_per_1000_words":round(1000*len(HEDGE_RX.findall(text))/total_words,3),
        "causal_density_per_1000_words":round(1000*len(CAUSAL_RX.findall(text))/total_words,3),
        "graph_digest":graph_digest(graph_artifact),
      },
      "locators":{"type":"document_inspection_segments","available":len(segs)},
      "warnings":list(inspection.get("warnings") or []),
      "policy":{"style_reference_is_not_evidence": role=="style", "evidence_requires_locator": role in {"evidence","both"}}
    }


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("inspection"); ap.add_argument("--role",choices=sorted(ROLES),required=True); ap.add_argument("--reference-id"); ap.add_argument("--graph-artifact")
    a=ap.parse_args()
    try:
        g=json.loads(Path(a.graph_artifact).read_text(encoding="utf-8")) if a.graph_artifact else None
        out=prepare(_load(Path(a.inspection)),a.role,a.reference_id,g)
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    except Exception as e:
        print(json.dumps({"ok":False,"schema":SCHEMA,"error":f"{type(e).__name__}: {e}"},ensure_ascii=False,indent=2)); return 2
if __name__=="__main__": raise SystemExit(main())
