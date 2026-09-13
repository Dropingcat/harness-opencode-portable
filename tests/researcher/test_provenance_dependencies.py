from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone

from researcher_core.challenge_resolution import ChallengeResolutionAssessment, ResolutionOutcome
from researcher_core.invalidation import ImpactState
from researcher_core.provenance_dependencies import (
    ProvenanceDependencyError,
    SourceIdentityBinding,
    assess_source_catalog_change,
    build_knowledge_dependencies,
    resolve_catalog_change,
    source_catalog_change_from_writer, reopen_from_source_catalog_change,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta, EvidenceSpan, Source
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation


class Clock:
    def now_ms(self): return 1789253000000


class ProvenanceDependencyTests(unittest.TestCase):
    def setUp(self):
        self.ids=EntityIdFactory(Clock(),random.Random(81));self.actor=ActorRef('AGENT','researcher')
        self.t=datetime(2026,9,12,22,30,tzinfo=timezone.utc);self.run=self.ids.new('RUN')
    def meta(self,prefix,version): return EntityMeta(self.ids.new(prefix),version,1,self.run,self.t,self.actor)

    def test_source_evidence_graph_and_resolution_compile(self):
        src=Source(self.meta('SRC','source/1.0'),'pdf','Paper','file.pdf','a'*64)
        evd=EvidenceSpan(self.meta('EVD','evidence-span/1.0'),src.meta.id,'a = 0.286 nm','p.4','b'*64)
        claim=self.ids.new('CLM')
        edge=GraphEdge(self.meta('EDG','graph-edge/1.0'),evd.meta.id,claim,EdgeKind.SUPPORTS,{})
        rrs=ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),self.ids.new('RCH'),self.ids.new('GAP'),1,ResolutionOutcome.RESOLVED,'resolved',(evd.meta.id,),(claim,))
        built=build_knowledge_dependencies(sources=(src,),evidence_spans=(evd,),graph_edges=(edge,),resolutions=(rrs,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        triples={(x.source_id.namespace,x.target_id.namespace,x.relation) for x in built.dependencies}
        self.assertIn(('SRC','EVD','contains_evidence'),triples)
        self.assertIn(('EVD','EDG','edge-source:supports'),triples)
        self.assertIn(('EDG','CLM','supports'),triples)
        self.assertIn(('EVD','RRS','justifies_resolution'),triples)

    def test_semantic_source_catalog_change_reaches_resolution(self):
        src=Source(self.meta('SRC','source/1.0'),'pdf','Paper','file.pdf','a'*64)
        evd=EvidenceSpan(self.meta('EVD','evidence-span/1.0'),src.meta.id,'text','p.1','b'*64)
        rrs=ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),self.ids.new('RCH'),self.ids.new('GAP'),1,ResolutionOutcome.RESOLVED,'resolved',(evd.meta.id,),())
        built=build_knowledge_dependencies(sources=(src,),evidence_spans=(evd,),resolutions=(rrs,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        cat={'ok':True,'schema':'source_catalog/1.1','source_id':'PAPER-1','change':'updated','old_sha256':'a'*64,'sha256':'c'*64,'semantic_changed':True,'change_class':'SEMANTIC'}
        impact=assess_source_catalog_change(catalog_result=cat,bindings=(SourceIdentityBinding('PAPER-1',src.meta.id,'a'*64),),dependencies=built.dependencies,target_resolution_id=rrs.meta.id,impact_meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertEqual(impact.state,ImpactState.REOPEN_REQUIRED)
        self.assertIn(rrs.meta.id,impact.invalidated_entity_ids)

    def test_byte_only_change_has_no_impact(self):
        src=self.ids.new('SRC')
        cat={'ok':True,'schema':'source_catalog/1.1','source_id':'PAPER-1','change':'updated','old_sha256':'a'*64,'sha256':'b'*64,'semantic_changed':False,'change_class':'BYTE_ONLY'}
        impact=assess_source_catalog_change(catalog_result=cat,bindings=(SourceIdentityBinding('PAPER-1',src,'a'*64),),dependencies=(),target_resolution_id=None,impact_meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertEqual(impact.state,ImpactState.NO_IMPACT)
        self.assertEqual(impact.changed_entity_ids,())

    def test_missing_or_ambiguous_identity_binding_fails_closed(self):
        change=source_catalog_change_from_writer({'ok':True,'schema':'source_catalog/1.1','source_id':'X','change':'updated','old_sha256':'a'*64,'sha256':'b'*64,'semantic_changed':True,'change_class':'SEMANTIC'})
        with self.assertRaises(ProvenanceDependencyError): resolve_catalog_change(change,())
        with self.assertRaises(ProvenanceDependencyError): resolve_catalog_change(change,(SourceIdentityBinding('X',self.ids.new('SRC')),SourceIdentityBinding('X',self.ids.new('SRC'))))

    def test_malformed_writer_catalog_result_fails_closed(self):
        base={'ok':True,'schema':'source_catalog/1.1','source_id':'X','change':'updated','old_sha256':'a'*64,'sha256':'b'*64,'semantic_changed':True,'change_class':'SEMANTIC'}
        with self.assertRaisesRegex(ProvenanceDependencyError, 'schema'):
            source_catalog_change_from_writer({**base, 'schema':'source_catalog/0.1'})
        with self.assertRaisesRegex(ProvenanceDependencyError, 'boolean'):
            source_catalog_change_from_writer({**base, 'semantic_changed':'false'})
        with self.assertRaisesRegex(ProvenanceDependencyError, 'SHA-256'):
            source_catalog_change_from_writer({**base, 'sha256':'z'*64})
        with self.assertRaisesRegex(ProvenanceDependencyError, 'mismatch'):
            source_catalog_change_from_writer({**base, 'semantic_changed':False})

    def test_trace_link_can_restore_resolution_dependency_without_assessment_object(self):
        evd=self.ids.new('EVD'); rrs=self.ids.new('RRS')
        trace=ResearchTraceLink(self.ids.new('RTL'),self.ids.new('RCD'),evd,ResearchTraceRelation.VALIDATED,self.run,self.t,self.actor,{'assessment_id':str(rrs)})
        built=build_knowledge_dependencies(trace_links=(trace,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        self.assertEqual(len(built.dependencies),1)
        self.assertEqual((built.dependencies[0].source_id,built.dependencies[0].target_id),(evd,rrs))

    def test_resolution_assessment_wins_over_duplicate_trace_dependency(self):
        evd=self.ids.new('EVD'); rrs_meta=self.meta('RRS','challenge-resolution/1.0')
        rrs=ChallengeResolutionAssessment(rrs_meta,self.ids.new('RCH'),self.ids.new('GAP'),1,ResolutionOutcome.RESOLVED,'resolved',(evd,),())
        trace=ResearchTraceLink(self.ids.new('RTL'),self.ids.new('RCD'),evd,ResearchTraceRelation.VALIDATED,self.run,self.t,self.actor,{'assessment_id':str(rrs_meta.id)})
        built=build_knowledge_dependencies(trace_links=(trace,),resolutions=(rrs,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        self.assertEqual(sum(1 for x in built.dependencies if x.source_id==evd and x.target_id==rrs_meta.id),1)

    def test_stale_catalog_version_binding_fails_closed(self):
        src=self.ids.new('SRC')
        cat={'ok':True,'schema':'source_catalog/1.1','source_id':'P','change':'updated','old_sha256':'a'*64,'sha256':'b'*64,'semantic_changed':True,'change_class':'SEMANTIC'}
        with self.assertRaisesRegex(ProvenanceDependencyError,'old_sha256'):
            assess_source_catalog_change(catalog_result=cat,bindings=(SourceIdentityBinding('P',src,'f'*64),),dependencies=(),target_resolution_id=None,impact_meta=self.meta('DIA','dependency-impact/1.0'))

    def test_semantic_catalog_change_reopens_existing_challenge_branch_end_to_end(self):
        from dataclasses import replace
        from researcher_core.knowledge_reconciliation import challenge_from_gap, materialize_challenge_card, ResearchChallengeStatus
        from researcher_core.r1_entities import Gap
        from researcher_core.r0.enums import GapState
        from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchPatch, ResearchRequest, SetCardStatusOperation, apply_research_patch, create_initial_dom

        request=ResearchRequest(self.meta('RRQ','research-request/1.0'),'Investigate source-sensitive claim')
        root=ResearchCard(self.meta('RCD','research-card/1.0'),request.meta.id,ResearchCardKind.OBJECTIVE,request.objective)
        dom=create_initial_dom(request,root,self.ids.new('RDM'))
        claim=self.ids.new('CLM')
        gap=Gap(self.ids.new('GAP'),'evidence_stability',(claim,),'blocking',(claim,),('refresh evidence',),GapState.NO_OPEN_GAPS)
        challenge=challenge_from_gap(gap,request.meta.id,self.meta('RCH','research-challenge/1.0'))
        fb=materialize_challenge_card(dom,challenge,parent_card_id=root.meta.id,card_id=self.ids.new('RCD'),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        card=fb.dom.cards[fb.card.meta.id]
        closed=apply_research_patch(fb.dom,ResearchPatch(self.ids.new('RPT'),request.meta.id,fb.dom.meta.revision,(SetCardStatusOperation(card.meta.id,card.meta.revision,ResearchCardStatus.COMPLETED),)),self.actor,self.ids,self.t,self.ids.new('OPR'),self.ids.new('TXN')).dom
        challenge=replace(challenge,meta=replace(challenge.meta,revision=2),status=ResearchChallengeStatus.RESOLVED)
        src=Source(self.meta('SRC','source/1.0'),'pdf','Paper','file.pdf','a'*64)
        evd=EvidenceSpan(self.meta('EVD','evidence-span/1.0'),src.meta.id,'text','p.1','b'*64)
        resolution=ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),challenge.meta.id,gap.id,1,ResolutionOutcome.RESOLVED,'resolved',(evd.meta.id,),())
        built=build_knowledge_dependencies(sources=(src,),evidence_spans=(evd,),resolutions=(resolution,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        cat={'ok':True,'schema':'source_catalog/1.1','source_id':'PAPER-1','change':'updated','old_sha256':'a'*64,'sha256':'c'*64,'semantic_changed':True,'change_class':'SEMANTIC'}
        out=reopen_from_source_catalog_change(catalog_result=cat,bindings=(SourceIdentityBinding('PAPER-1',src.meta.id,'a'*64),),dependencies=built.dependencies,dom=closed,challenge=challenge,source_entity=gap,resolution=resolution,challenge_card_id=card.meta.id,prior_iterations=(),patch_id=self.ids.new('RPT'),impact_meta=self.meta('DIA','dependency-impact/1.0'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(out.challenge.status.value,'REOPENED')
        self.assertEqual(out.dom.cards[card.meta.id].status.value,'ACTIVE')
        self.assertEqual(out.source_entity.status,GapState.OPEN_BLOCKING_GAPS)
        self.assertEqual(out.iteration.iteration_index,1)

    def test_real_writer_source_catalog_update_drives_researcher_impact(self):
        import tempfile
        from scripts.writer.sources.source_catalog import by_path_or_sha, upsert
        src=Source(self.meta('SRC','source/1.0'),'pdf','Paper','file.pdf','a'*64)
        evd=EvidenceSpan(self.meta('EVD','evidence-span/1.0'),src.meta.id,'text','p.1','b'*64)
        rrs=ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),self.ids.new('RCH'),self.ids.new('GAP'),1,ResolutionOutcome.RESOLVED,'resolved',(evd.meta.id,),())
        built=build_knowledge_dependencies(sources=(src,),evidence_spans=(evd,),resolutions=(rrs,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        with tempfile.TemporaryDirectory() as td:
            db=str(__import__('pathlib').Path(td)/'catalog.sqlite')
            upsert(db,{'source_id':'PAPER-X','sha256':'a'*64,'path':'paper.pdf','metadata':{'normalized_text_hash':'1'*64}})
            changed=upsert(db,{'source_id':'PAPER-X','sha256':'c'*64,'path':'paper.pdf','metadata':{'normalized_text_hash':'2'*64}})
            impact=assess_source_catalog_change(catalog_result=changed,bindings=(SourceIdentityBinding('PAPER-X',src.meta.id,'a'*64),),dependencies=built.dependencies,target_resolution_id=rrs.meta.id,impact_meta=self.meta('DIA','dependency-impact/1.0'))
            self.assertEqual(changed['change_class'],'SEMANTIC')
            self.assertEqual(impact.state,ImpactState.REOPEN_REQUIRED)
            self.assertIsNone(by_path_or_sha(db, 'paper.pdf', 'a'*64))

    def test_writer_source_catalog_rejects_non_hex_sha256(self):
        import tempfile
        from scripts.writer.sources.source_catalog import upsert
        with tempfile.TemporaryDirectory() as td:
            db=str(__import__('pathlib').Path(td)/'catalog.sqlite')
            with self.assertRaisesRegex(ValueError, 'sha256'):
                upsert(db, {'source_id':'PAPER-X','sha256':'z'*64})


if __name__=='__main__': unittest.main()

class GraphEdgeLifecycleDependencyTests(unittest.TestCase):
    def setUp(self):
        import random
        from datetime import datetime, timezone
        from researcher_core.r0.ids import EntityIdFactory
        class Clock:
            def now_ms(self): return 1789250100000
        self.ids=EntityIdFactory(Clock(),random.Random(53));self.actor=ActorRef('AGENT','researcher')
        self.t=datetime(2026,9,12,21,10,tzinfo=timezone.utc);self.run=self.ids.new('RUN')
    def meta(self,prefix,version,revision=1): return EntityMeta(self.ids.new(prefix),version,revision,self.run,self.t,self.actor)
    def test_stale_edge_compiles_stale_dependencies_and_terminal_edge_is_excluded(self):
        from researcher_core.r0.graph import GraphEdgeState
        evd=self.ids.new('EVD');claim=self.ids.new('CLM')
        stale=GraphEdge(self.meta('EDG','graph-edge/1.0'),evd,claim,EdgeKind.SUPPORTS,{},GraphEdgeState.STALE)
        build=build_knowledge_dependencies(graph_edges=(stale,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        self.assertTrue(build.dependencies)
        self.assertTrue(all(x.state.value=='STALE' for x in build.dependencies))
        dead=GraphEdge(self.meta('EDG','graph-edge/1.0'),evd,claim,EdgeKind.SUPPORTS,{},GraphEdgeState.INVALIDATED)
        build2=build_knowledge_dependencies(graph_edges=(dead,),id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        self.assertFalse(build2.dependencies)
        self.assertTrue(any(x.startswith('TERMINAL_EDGE_EXCLUDED') for x in build2.diagnostics))
