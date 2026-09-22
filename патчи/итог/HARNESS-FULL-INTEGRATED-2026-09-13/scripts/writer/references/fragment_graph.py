from __future__ import annotations
import hashlib,json
from typing import Any
from scripts.writer.extraction.hybrid import hybrid_extract_paragraph
from scripts.writer.analysis.graph_builder import build_paragraph_graphs
from scripts.writer.references.graph_profile import digest
SCHEMA='reference_fragment_graph/1.0'
VERSION='hybrid+graph_registry_v0.3'

def build(fragment:dict[str,Any])->dict[str,Any]:
    text=str(fragment.get('excerpt') or '')
    if not text.strip():raise ValueError('fragment excerpt required')
    loc=str(fragment.get('locator') or '')
    fid=str(fragment.get('fragment_id') or '')
    art=hybrid_extract_paragraph(text,fid or 'reference-fragment')
    graphs=build_paragraph_graphs(art)
    source_span={
        'source_id':fragment.get('source_id'),'source_sha256':fragment.get('source_sha256'),
        'locator':loc,'span':fragment.get('span'),'normalized_text_hash':fragment.get('normalized_text_hash')}
    # provenance belongs on every graph node/edge; local start/end remain fragment-relative.
    for g in (graphs.get('graphs') or {}).values():
        for n in g.get('nodes') or []:
            n.setdefault('props',{})['source_span']=source_span
        for e in g.get('edges') or []:
            e.setdefault('props',{})['source_span']=source_span
    dg=digest({'graphs':{fid:graphs}})
    key=hashlib.sha256(json.dumps({'source_sha256':fragment.get('source_sha256'),'locator':loc,'text_hash':fragment.get('normalized_text_hash'),'version':VERSION},sort_keys=True).encode()).hexdigest()
    return {'ok':True,'schema':SCHEMA,'fragment_id':fid,'cache_key':key,'extractor_version':VERSION,'source_span':source_span,'fingerprint':dg,'graphs':graphs}
