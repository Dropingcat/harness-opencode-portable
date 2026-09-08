#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, requests
DOI_RX=re.compile(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)',re.I)
def doi_of(s):
    m=DOI_RX.search(s.strip()); return m.group(1).rstrip('.,;)').lower() if m else None
def crossref(doi):
    r=requests.get('https://api.crossref.org/works/'+doi,timeout=15,headers={'User-Agent':'opencode-harness-source-resolver/1.0'}); r.raise_for_status(); m=r.json()['message']; return {'doi':m.get('DOI'),'title':(m.get('title') or [None])[0],'authors':[' '.join(filter(None,[a.get('given'),a.get('family')])) for a in m.get('author',[])],'publisher':m.get('publisher'),'type':m.get('type'),'url':m.get('URL')}
def openalex(query):
    r=requests.get('https://api.openalex.org/works',params={'search':query,'per-page':5},timeout=15); r.raise_for_status(); return [{'id':x.get('id'),'doi':x.get('doi'),'title':x.get('display_name'),'year':x.get('publication_year'),'type':x.get('type')} for x in r.json().get('results',[])]
def unpaywall(doi):
    email=os.environ.get('UNPAYWALL_EMAIL');
    if not email: return {'available':False,'reason':'UNPAYWALL_EMAIL not set'}
    r=requests.get('https://api.unpaywall.org/v2/'+doi,params={'email':email},timeout=15); r.raise_for_status(); j=r.json(); best=j.get('best_oa_location') or {}; return {'available':bool(j.get('is_oa')),'url':best.get('url_for_pdf') or best.get('url')}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('candidate'); ap.add_argument('--offline',action='store_true'); a=ap.parse_args(); doi=doi_of(a.candidate)
    out={'ok':True,'schema':'canonical_source_candidate.v1','candidate':a.candidate,'doi_candidate':doi,'metadata':{},'oa':{},'alternatives':[],'warnings':[]}
    if a.offline: print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    try:
        if doi: out['metadata']=crossref(doi); out['oa']=unpaywall(doi)
        else: out['alternatives']=openalex(a.candidate); out['warnings'].append('no_doi_candidate')
    except Exception as e: out['ok']=False; out['error']=f'{e.__class__.__name__}: {e}'
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out['ok'] else 2
if __name__=='__main__': raise SystemExit(main())
