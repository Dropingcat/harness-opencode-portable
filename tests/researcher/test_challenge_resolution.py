from __future__ import annotations
import random, unittest, sqlite3
from datetime import datetime, timezone

from researcher_core.challenge_resolution import (
    ChallengeResolutionAssessment, ChallengeResolutionError, ChallengeResolutionRepository, ConflictResolutionMode,
    ResolutionOutcome, reconcile_challenge_resolution,
)
from researcher_core.knowledge_reconciliation import (
    ResearchChallengeStatus, challenge_from_conflict, challenge_from_gap, materialize_challenge_card,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, GapState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.research_planning import (
    AddCardOperation, ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchPatch,
    ResearchRequest, apply_research_patch, create_initial_dom,
)
from researcher_core.research_planning_runtime import ResearchTraceRelation

class Clock:
    def now_ms(self): return 1789245000000

class ChallengeResolutionTests(unittest.TestCase):
    def setUp(self):
        self.ids=EntityIdFactory(Clock(), random.Random(29)); self.actor=ActorRef('AGENT','researcher')
        self.created=datetime(2026,9,12,16,0,tzinfo=timezone.utc); self.run=self.ids.new('RUN')
        self.req=ResearchRequest(EntityMeta(self.ids.new('RRQ'),'research-request/1.0',1,self.run,self.created,self.actor),'Исследовать peak shift')
        root=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',1,self.run,self.created,self.actor),self.req.meta.id,ResearchCardKind.OBJECTIVE,self.req.objective)
        dom=create_initial_dom(self.req,root,self.ids.new('RDM'))
        task=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',1,self.run,self.created,self.actor),self.req.meta.id,ResearchCardKind.TASK,'Проверить shift',root.meta.id,dimensions={'capability':'evidence.verify'})
        self.dom=apply_research_patch(dom,ResearchPatch(self.ids.new('RPT'),self.req.meta.id,1,(AddCardOperation(task),)),self.actor,self.ids,self.created,self.ids.new('OPR'),self.ids.new('TXN')).dom
        self.task=task; self.claim1=self.ids.new('CLM'); self.claim2=self.ids.new('CLM')

    def meta(self,prefix,version): return EntityMeta(self.ids.new(prefix),version,1,self.run,self.created,self.actor)

    def gap_branch(self, state=GapState.OPEN_BLOCKING_GAPS):
        gap=Gap(self.ids.new('GAP'),'residual_stress_not_excluded',(self.claim1,),'blocking',(self.claim1,),('separate stress and composition',),state)
        ch=challenge_from_gap(gap,self.req.meta.id,self.meta('RCH','research-challenge/1.0'))
        fb=materialize_challenge_card(self.dom,ch,parent_card_id=self.task.meta.id,card_id=self.ids.new('RCD'),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        return gap,ch,fb

    def assessment(self,ch,src,outcome,**kw):
        return ChallengeResolutionAssessment(self.meta('RRS','challenge-resolution/1.0'),ch.meta.id,src.id,ch.meta.revision,outcome,kw.pop('rationale','checked'),**kw)

    def test_resolved_gap_closes_gap_challenge_and_card(self):
        gap,ch,fb=self.gap_branch(); ev=self.ids.new('EVD')
        a=self.assessment(ch,gap,ResolutionOutcome.RESOLVED,evidence_refs=(ev,))
        r=reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=gap,assessment=a,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(r.source_entity.status,GapState.NO_OPEN_GAPS); self.assertEqual(r.challenge.status,ResearchChallengeStatus.RESOLVED); self.assertEqual(r.challenge.meta.revision, ch.meta.revision+1)
        self.assertEqual(r.dom.cards[fb.card.meta.id].status,ResearchCardStatus.COMPLETED)
        self.assertIn(ResearchTraceRelation.RESOLVED_BY,{x.relation for x in r.trace_links})

    def test_blocked_gap_keeps_knowledge_open_and_blocks_card(self):
        gap,ch,fb=self.gap_branch(); a=self.assessment(ch,gap,ResolutionOutcome.BLOCKED,remaining_requirements=('primary source missing',))
        r=reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=gap,assessment=a,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(r.source_entity.status,GapState.OPEN_BLOCKING_GAPS); self.assertEqual(r.challenge.status,ResearchChallengeStatus.BLOCKED)
        self.assertEqual(r.dom.cards[fb.card.meta.id].status,ResearchCardStatus.BLOCKED)

    def test_reopened_resolved_gap_becomes_open_again(self):
        gap,ch,fb=self.gap_branch(GapState.NO_OPEN_GAPS); ch=__import__('dataclasses').replace(ch,status=ResearchChallengeStatus.RESOLVED)
        a=self.assessment(ch,gap,ResolutionOutcome.REOPENED,remaining_requirements=('new contradictory evidence',))
        r=reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=gap,assessment=a,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(r.source_entity.status,GapState.OPEN_BLOCKING_GAPS); self.assertEqual(r.challenge.status,ResearchChallengeStatus.REOPENED)
        self.assertEqual(r.dom.cards[fb.card.meta.id].status,ResearchCardStatus.ACTIVE)

    def test_scope_mismatch_can_resolve_conflict_without_claiming_substantive_agreement(self):
        c=Conflict(self.ids.new('CNF'),(self.claim1,self.claim2),(self.ids.new('EVD'),self.ids.new('EVD')),'scope_mismatch_or_real_contradiction',ConflictState.CONFLICT_UNRESOLVED)
        ch=challenge_from_conflict(c,self.req.meta.id,self.meta('RCH','research-challenge/1.0'))
        fb=materialize_challenge_card(self.dom,ch,parent_card_id=self.task.meta.id,card_id=self.ids.new('RCD'),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        a=self.assessment(ch,c,ResolutionOutcome.RESOLVED,conflict_mode=ConflictResolutionMode.SCOPE_MISMATCH,rationale='different material and temperature scopes')
        r=reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=c,assessment=a,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(r.source_entity.status,ConflictState.NO_DIRECT_CONFLICT); self.assertEqual(r.assessment.conflict_mode,ConflictResolutionMode.SCOPE_MISMATCH)

    def test_insufficient_evidence_cannot_resolve_conflict(self):
        c=Conflict(self.ids.new('CNF'),(self.claim1,self.claim2),(),'x',ConflictState.CONFLICT_UNRESOLVED)
        ch=challenge_from_conflict(c,self.req.meta.id,self.meta('RCH','research-challenge/1.0'))
        fb=materialize_challenge_card(self.dom,ch,parent_card_id=self.task.meta.id,card_id=self.ids.new('RCD'),patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        a=self.assessment(ch,c,ResolutionOutcome.RESOLVED,conflict_mode=ConflictResolutionMode.INSUFFICIENT_EVIDENCE)
        with self.assertRaises(ChallengeResolutionError):
            reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=c,assessment=a,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_resolution_assessment_persists_in_existing_sqlite_substrate(self):
        gap,ch,fb=self.gap_branch(); a=self.assessment(ch,gap,ResolutionOutcome.STILL_OPEN,remaining_requirements=('more evidence',))
        conn=sqlite3.connect(':memory:'); repo=ChallengeResolutionRepository(conn); repo.save(a)
        self.assertEqual(repo.load(a.meta.id),a); conn.close()

    def test_stale_challenge_assessment_fails_closed(self):
        gap,ch,fb=self.gap_branch(); a=self.assessment(ch,gap,ResolutionOutcome.STILL_OPEN,remaining_requirements=('more evidence',))
        from dataclasses import replace
        stale=replace(a, expected_challenge_revision=ch.meta.revision+1)
        with self.assertRaisesRegex(ChallengeResolutionError, "challenge revision mismatch"):
            reconcile_challenge_resolution(dom=fb.dom,challenge=ch,source_entity=gap,assessment=stale,challenge_card_id=fb.card.meta.id,patch_id=self.ids.new('RPT'),actor=self.actor,id_factory=self.ids,timestamp=self.created,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

if __name__=='__main__': unittest.main()
