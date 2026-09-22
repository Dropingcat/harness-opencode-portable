#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha256_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('path'); ap.add_argument('--preview-dir'); a=ap.parse_args(); p=Path(a.path).resolve()
    try:
        if p.suffix.lower() not in {'.tif','.tiff'}: raise ValueError('current capsule supports TIFF only')
        import tifffile
        frames=[]; warnings=['vendor_private_tags_preserved_but_not_semantically_promoted','unknown_units_remain_unknown']
        preview_paths=[]
        with tifffile.TiffFile(p) as tf:
            for i,page in enumerate(tf.pages):
                tags={}
                for tag in page.tags.values():
                    try:
                        v=tag.value
                        if isinstance(v,(bytes,bytearray)): v={'binary_length':len(v),'hex_prefix':bytes(v[:32]).hex()}
                        elif isinstance(v,(tuple,list)) and len(v)>64: v=list(v[:64])+['<truncated>']
                        elif not isinstance(v,(str,int,float,bool,list,tuple,dict,type(None))): v=str(v)
                        tags[str(tag.name)]={'code':int(tag.code),'value':v}
                    except Exception as e: tags[str(getattr(tag,'name','unknown'))]={'error':str(e)}
                frames.append({'frame':i,'shape':list(page.shape),'dtype':str(page.dtype),'tags':tags})
                if a.preview_dir:
                    try:
                        from PIL import Image
                        out=Path(a.preview_dir); out.mkdir(parents=True,exist_ok=True); q=out/f'{p.stem}_frame_{i:04d}.png'; Image.fromarray(page.asarray()).save(q); preview_paths.append(str(q.resolve()))
                    except Exception as e: warnings.append(f'preview_failed_frame_{i}:{e.__class__.__name__}')
        out={'ok':True,'schema':'scientific-image-inspection/1.0','path':str(p),'sha256':sha256_file(p),'media_type':'image/tiff','frames':frames,'previews':preview_paths,'observational_only':True,'phase_identification_allowed':False,'warnings':warnings}
        print(json.dumps(out,ensure_ascii=False,indent=2,default=str)); return 0
    except Exception as e:
        print(json.dumps({'ok':False,'schema':'scientific-image-inspection/1.0','path':str(p),'error':f'{e.__class__.__name__}: {e}'},ensure_ascii=False,indent=2)); return 2
if __name__=='__main__': raise SystemExit(main())
