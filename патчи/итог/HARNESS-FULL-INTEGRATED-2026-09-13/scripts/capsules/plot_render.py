#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('input'); ap.add_argument('--x',required=True); ap.add_argument('--y',required=True); ap.add_argument('--kind',choices=['scatter','line'],default='scatter'); ap.add_argument('--output',required=True); ap.add_argument('--title'); ap.add_argument('--xlabel'); ap.add_argument('--ylabel'); args=ap.parse_args()
    import matplotlib.pyplot as plt
    p=Path(args.input); rows=[]
    if p.suffix.lower()=='.csv':
        with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    else:
        data=json.loads(p.read_text(encoding='utf-8')); rows=data if isinstance(data,list) else data.get('rows',[])
    x=[float(r[args.x]) for r in rows]; y=[float(r[args.y]) for r in rows]
    fig,ax=plt.subplots()
    if args.kind=='scatter': ax.scatter(x,y)
    else: ax.plot(x,y)
    if args.title: ax.set_title(args.title)
    ax.set_xlabel(args.xlabel or args.x); ax.set_ylabel(args.ylabel or args.y); ax.grid(True,alpha=.25)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(out,dpi=200); plt.close(fig)
    h=hashlib.sha256(out.read_bytes()).hexdigest()
    print(json.dumps({'ok':True,'schema':'plot_artifact.v1','output':str(out.resolve()),'sha256':h,'points':len(x),'kind':args.kind,'x':args.x,'y':args.y},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
