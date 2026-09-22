#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
from typing import Any

SCHEMA='reference_graph_digest/1.0'

def digest(graph_artifact:dict[str,Any]|None)->dict[str,Any]:
    if not graph_artifact:
        return {'schema':SCHEMA,'available':False,'graph_count':0,'node_count':0,'edge_count':0,'graph_ids':[], 'node_types':{},'edge_relations':{},'motifs':[]}
    graphs=graph_artifact.get('graphs') or {}
    node_types=Counter(); edge_rel=Counter(); graph_ids=Counter(); node_count=edge_count=0
    def consume(gid:str,g:dict[str,Any]):
        nonlocal node_count,edge_count
        # Supports writer_core.graphs.v1 paragraph payload {graphs:{Gx:{nodes,edges}}}
        nested=g.get('graphs') if isinstance(g,dict) else None
        if isinstance(nested,dict):
            for ngid,ng in nested.items(): consume(str(ngid),ng if isinstance(ng,dict) else {})
            return
        nodes=g.get('nodes') or []; edges=g.get('edges') or []
        if nodes or edges: graph_ids[gid]+=1
        for n in nodes:
            if isinstance(n,dict): node_types[str(n.get('type') or '?')]+=1; node_count+=1
        for e in edges:
            if isinstance(e,dict): edge_rel[str(e.get('relation') or '?')]+=1; edge_count+=1
    if isinstance(graphs,dict):
        for pid,g in graphs.items(): consume(str(pid),g if isinstance(g,dict) else {})
    # Legacy flat artifact support
    if isinstance(graph_artifact.get('nodes'),list) or isinstance(graph_artifact.get('edges'),list): consume('flat',graph_artifact)
    motifs=[]
    for rel,n in edge_rel.most_common(12): motifs.append({'kind':'edge_relation','value':rel,'count':n})
    for typ,n in node_types.most_common(8): motifs.append({'kind':'node_type','value':typ,'count':n})
    return {'schema':SCHEMA,'available':bool(node_count or edge_count),'graph_count':sum(graph_ids.values()),'node_count':node_count,'edge_count':edge_count,
            'graph_ids':sorted(graph_ids),'graph_instances':dict(sorted(graph_ids.items())),
            'node_types':dict(node_types.most_common()),'edge_relations':dict(edge_rel.most_common()),
            'node_type_share':{k:round(v/max(1,node_count),6) for k,v in node_types.most_common()},
            'edge_relation_share':{k:round(v/max(1,edge_count),6) for k,v in edge_rel.most_common()},
            'motifs':motifs}
