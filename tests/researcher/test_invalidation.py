from __future__ import annotations
import random, sqlite3, unittest
from dataclasses import replace
from datetime import datetime, timezone

from researcher_core.challenge_resolution import ChallengeResolutionAssessment, ConflictResolutionMode, ResolutionOutcome
from researcher_core.invalidation import (
    ChallengeIteration, DependencyImpactAssessment, DependencyStrength, ImpactState, InvalidationError,
    InvalidationRepository, IterationState, KnowledgeDependency, assess_dependency_impact, reopen_from_impact,
)
from researcher_core.knowledge_reconciliation import ResearchChallengeStatus, challenge_from_conflict, challenge_from_gap, materialize_challenge_card
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, GapState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.research_planning import (
    AddCardOperation, ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchPatch, ResearchRequest,
    SetCardStatusOperation, apply_research_patch, create_initial_dom,
)

class Clock:
    def now_ms(self): return 1789249000000

class InvalidationTests(unittest.TestCase):
    def setUp(self):
        self.ids=EntityIdFactory(Clock(),random.Random(41));self.actor=ActorRef('AGENT','researcher')
        self.t=datetime(2026,9,12,20,0,tzinfo=timezone.utc);self.run=self.ids.new('RUN')
        self.req=ResearchRequest(self.meta('RRQ','research-request/1.0'),'Исследовать peak shift')
        root=ResearchCard(self.meta('RCD','research-card/1.0'),self.req.meta.id,ResearchCardKind.OBJECTIVE,self.req.objective)
        dom=create_initial_dom(self.req,root,self.ids.new('RDM'))
        task=ResearchCard(self.meta('RCD','research-card/1.0'),self.req.meta.id,ResearchCardKind.TASK,'Проверить XRD',root.meta.id,dimensions={'capability':'evidence.verify'})
        self.dom=apply_research_patch(dom,ResearchPatch(self.ids.new('RPT'),self.req.meta.id,1,(AddCardOperation(task),)),self.actor,self.ids,self.t,self.ids.new('OPR'),self.ids.new('TXN')).dom
        self.task=task;self.claim1=self.ids.new('CLM');self.claim2=self.ids.new('CLM')
    def meta(self,prefix,version,revision=1): return EntityMeta(self.ids.new(prefix),version,revision,self.run,self.t,self.actor)
    def dep(self,source,target,*,strength=DependencyStrength.HARD,group='support',min_active=1,relation='supports',**metadata):
        return KnowledgeDependency(self.meta('KDP','knowledge-dependency/1.0'),source,target,relation,strength,group,min_active,metadata=metadata)
    def resolved_gap_branch(self):
        gap=Gap(self.ids.new('GAP'),'residual_stress_not_excluded',(self.claim1,),'blocking',(self.claim1,),('separate stress and composition',),GapState.NO_OPEN_GAPS)
        ch=challenge_from_gap(gap,self.req.meta.id,self.meta('RCH','research-challenge/1.0'))
        fb=materialize_challenge_card(self.dom,ch,parent_card_id=self.task.meta.id,card_id=self.ids.new('RCD'),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        card=fb.dom.cards[fb.card.meta.id]
        closed=apply_research_patch(fb.dom,ResearchPatch(self.ids.new('RPT'),self.req.meta.id,fb.dom.meta.revision,(SetCardStatusOperation(card.meta.id,card.meta.revision,ResearchCardStatus.COMPLETED),)),self.actor,self.ids,self.t,self.ids.new('OPR'),self.ids.new('TXN')).dom
        ch=replace(ch,meta=replace(ch.meta,revision=2),status=ResearchChallengeStatus.RESOLVED)
        r=ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),ch.meta.id,gap.id,1,ResolutionOutcome.RESOLVED,'resolved',evidence_refs=())
        return gap,ch,closed,fb.card.meta.id,r

    def test_redundant_evidence_stales_without_reopen(self):
        gap,ch,dom,card,res=self.resolved_gap_branch(); e1=self.ids.new('EVD');e2=self.ids.new('EVD')
        deps=(self.dep(e1,res.meta.id,min_active=1),self.dep(e2,res.meta.id,min_active=1))
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=deps,target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertEqual(impact.state,ImpactState.REVALIDATION_REQUIRED)
        out=reopen_from_impact(dom=dom,challenge=ch,source_entity=gap,resolution=res,impact=impact,challenge_card_id=card,prior_iterations=(),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertIsNone(out.iteration);self.assertEqual(out.challenge.status,ResearchChallengeStatus.RESOLVED);self.assertEqual(out.dom,dom)

    def test_sole_hard_evidence_reopens_same_branch(self):
        gap,ch,dom,card,res=self.resolved_gap_branch();e1=self.ids.new('EVD')
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(self.dep(e1,res.meta.id),),target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertEqual(impact.state,ImpactState.REOPEN_REQUIRED)
        out=reopen_from_impact(dom=dom,challenge=ch,source_entity=gap,resolution=res,impact=impact,challenge_card_id=card,prior_iterations=(),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(out.source_entity.status,GapState.OPEN_BLOCKING_GAPS);self.assertEqual(out.challenge.status,ResearchChallengeStatus.REOPENED)
        self.assertEqual(out.dom.cards[card].status,ResearchCardStatus.ACTIVE);self.assertEqual(out.iteration.iteration_index,1)

    def test_relation_only_invalidation_does_not_invalidate_endpoint_claims(self):
        edge=self.ids.new('EDG');e1=self.ids.new('EVD')
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(self.dep(e1,edge,relation='supports-edge'),),target_resolution_id=None,meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertIn(edge,impact.stale_relation_ids);self.assertNotIn(self.claim1,impact.invalidated_entity_ids);self.assertEqual(impact.state,ImpactState.STALE_ONLY)

    def test_contextual_scope_nonoverlap_does_not_reopen(self):
        gap,ch,dom,card,res=self.resolved_gap_branch();e1=self.ids.new('EVD')
        d=self.dep(e1,res.meta.id,strength=DependencyStrength.CONTEXTUAL,scope_overlap=False)
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(d,),target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        self.assertEqual(impact.state,ImpactState.NO_IMPACT)

    def test_stale_old_resolution_revision_is_rejected(self):
        gap,ch,dom,card,res=self.resolved_gap_branch();e1=self.ids.new('EVD')
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(self.dep(e1,res.meta.id),),target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        stale=replace(res,expected_challenge_revision=2)
        with self.assertRaisesRegex(InvalidationError,'current resolved challenge revision'):
            reopen_from_impact(dom=dom,challenge=ch,source_entity=gap,resolution=stale,impact=impact,challenge_card_id=card,prior_iterations=(),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_iterations_persist_as_history(self):
        gap,ch,dom,card,res=self.resolved_gap_branch();e1=self.ids.new('EVD')
        old=ChallengeIteration(self.meta('RIT','challenge-iteration/1.0'),ch.meta.id,1,IterationState.RESOLVED,(res.meta.id,),res.meta.id,None)
        impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(self.dep(e1,res.meta.id),),target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        out=reopen_from_impact(dom=dom,challenge=ch,source_entity=gap,resolution=res,impact=impact,challenge_card_id=card,prior_iterations=(old,),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(out.iteration.iteration_index,2)
        conn=sqlite3.connect(':memory:');repo=InvalidationRepository(conn);repo.save(old,out.iteration,impact)
        hist=repo.iterations_for_challenge(ch.meta.id);self.assertEqual([x['iteration_index'] for x in hist],[1,2]);conn.close()

    def test_unrelated_branch_is_unchanged(self):
        gap,ch,dom,card,res=self.resolved_gap_branch(); root=dom.root_card_id
        other=ResearchCard(self.meta('RCD','research-card/1.0'),self.req.meta.id,ResearchCardKind.TASK,'Независимая ветвь',root,dimensions={'capability':'corpus.search'})
        dom2=apply_research_patch(dom,ResearchPatch(self.ids.new('RPT'),self.req.meta.id,dom.meta.revision,(AddCardOperation(other),)),self.actor,self.ids,self.t,self.ids.new('OPR'),self.ids.new('TXN')).dom
        before=dom2.cards[other.meta.id]
        e1=self.ids.new('EVD');impact=assess_dependency_impact(changed_entity_ids=(e1,),dependencies=(self.dep(e1,res.meta.id),),target_resolution_id=res.meta.id,meta=self.meta('DIA','dependency-impact/1.0'))
        out=reopen_from_impact(dom=dom2,challenge=ch,source_entity=gap,resolution=res,impact=impact,challenge_card_id=card,prior_iterations=(),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(out.dom.cards[other.meta.id],before)

if __name__=='__main__': unittest.main()
