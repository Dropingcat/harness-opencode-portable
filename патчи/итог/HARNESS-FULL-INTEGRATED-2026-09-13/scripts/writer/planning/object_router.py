#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

SCHEMA="writing_object_decision/1.0"
KINDS={"dissertation","article","chapter","technical_report","abstract","author_abstract","unknown"}

def decide(text:str, explicit_kind:str|None=None)->dict[str,Any]:
    if explicit_kind:
        if explicit_kind not in KINDS: raise ValueError("unsupported explicit kind")
        return {"ok":True,"schema":SCHEMA,"kind":explicit_kind,"confidence":1.0,"authority":"explicit_user_or_contract","signals":[]}
    s=text[:50000]
    signals=[]; scores={k:0 for k in KINDS}
    pats={
      "dissertation":[r"диссертац",r"\bdissertation\b",r"\bthesis\b",r"Ph\.?D",r"doctor of",r"genehmigte\s+Abhandlung",r"zur\s+Erlangung"],
      "article":[r"\babstract\b",r"\bkeywords\b",r"\bdoi\b",r"journal|vol\.?\s*\d"],
      "technical_report":[r"implementation|architecture|migration|review report|отч[её]т|архитектур"],
      "author_abstract":[r"автореферат",r"на соискание ученой степени.*автореф"],
    }
    for kind,rxs in pats.items():
        for rx in rxs:
            if re.search(rx,s,re.I): scores[kind]+=1; signals.append({"kind":kind,"pattern":rx})
    best=max(scores,key=scores.get)
    top=scores[best]
    if top==0: best="unknown"; conf=.25
    else:
        second=sorted(scores.values(),reverse=True)[1]
        conf=min(.95,.55+.08*top+.05*max(0,top-second))
    return {"ok":True,"schema":SCHEMA,"kind":best,"confidence":round(conf,3),"authority":"deterministic_classifier","signals":signals,"scores":scores,
            "requires_confirmation":conf<.75}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--kind",choices=sorted(KINDS)); a=ap.parse_args()
    p=Path(a.path)
    if p.suffix.lower()=='.json':
        raw=json.loads(p.read_text(encoding='utf-8'))
        if raw.get('schema')=='document_inspection.v1':
            text='\n'.join(str(x.get('text') or '') for x in (raw.get('segments') or []))
        else:
            text=json.dumps(raw,ensure_ascii=False)
    else:
        text=p.read_text(encoding='utf-8',errors='replace')
    print(json.dumps(decide(text,a.kind),ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
