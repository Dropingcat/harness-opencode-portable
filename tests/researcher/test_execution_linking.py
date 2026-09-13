from __future__ import annotations
import random, sqlite3, unittest
from datetime import datetime, timezone
from decimal import Decimal
from researcher_core.capsules import CapsuleObservation
from researcher_core.execution_admission import admit_execution_proposal, compile_local_execution_admission
from researcher_core.execution_linking import (
    AdmissionIdentityMap, EndpointRefKind, ExecutionLinkingError, RelationEndpointRef,
    SemanticRelationProposal, ExecutionLinkingAuditRepository, admit_semantic_relations, build_admission_identity_map,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import ClaimProposal, EntityMeta, EvidenceSpan, QuantityProposal, Source
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, SequenceClock
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.task_execution import ExecutionOwner, TaskExecutionResult, TaskExecutionStatus

class Clock:
    def now_ms(self): return 1789256000000

class ExecutionLinkingTests(unittest.TestCase):
    def setUp(self):
        self.ids=EntityIdFactory(Clock(), random.Random(71)); self.actor=ActorRef('AGENT','researcher')
        self.t=datetime(2026,9,12,22,0,tzinfo=timezone.utc); self.run=self.ids.new('RUN'); self.req=self.ids.new('RRQ')
        root=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',1,self.run,self.t,self.actor),self.req,ResearchCardKind.OBJECTIVE,'Objective')
        self.task=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',3,self.run,self.t,self.actor),self.req,ResearchCardKind.TASK,'Task',parent_id=root.meta.id,status=ResearchCardStatus.COMPLETED,dimensions={'capability':'fixture'})
        self.dom=ResearchDOM(EntityMeta(self.ids.new('RDM'),'research-dom/1.0',2,self.run,self.t,self.actor),self.req,root.meta.id,{root.meta.id:root,self.task.meta.id:self.task},())
        self.registry=InMemoryClaimRegistry(SequenceClock(1789256001000),CycleRandom())

    def _admit(self, payload):
        obs=CapsuleObservation(self.ids.new('OPR'),'fixture','fixture','proposal-observation/1.0',payload,{'fixture':True})
        ter=TaskExecutionResult(EntityMeta(self.ids.new('TER'),'task-execution-result/1.0',1,self.run,self.t,self.actor),self.ids.new('TEP'),self.task.meta.id,2,TaskExecutionStatus.SUCCEEDED,ExecutionOwner.RESEARCHER,'fixture',observation=obs)
        p=compile_local_execution_admission(result=ter,id_factory=self.ids,actor=self.actor,created_at=self.t)
        r,_,_=admit_execution_proposal(dom=self.dom,proposal=p,registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        m=build_admission_identity_map(proposal=p,receipt=r,registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t)
        return p,r,m

    def _rp(self,p,kind,s_kind,s,t_kind,t):
        return SemanticRelationProposal(EntityMeta(self.ids.new('SRP'),'semantic-relation-proposal/1.0',1,self.run,self.t,self.actor),p.meta.id,RelationEndpointRef(s_kind,s),RelationEndpointRef(t_kind,t),kind,'explicit adapter relation')

    def test_identity_map_resolves_claim_and_quantity_temp_ids(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        self.assertEqual(m.temp_to_canonical['tmp-c'].namespace,'CLM'); self.assertEqual(m.temp_to_canonical['tmp-q'].namespace,'QTY')

    def test_explicit_quantity_relation_creates_canonical_edge(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        rp=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        receipt,result,links=admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        edge=self.registry.state[result.accepted_ids[0]]; self.assertEqual(edge.source_id,m.temp_to_canonical['tmp-q']); self.assertEqual(edge.target_id,m.temp_to_canonical['tmp-c']); self.assertEqual(edge.edge_kind,EdgeKind.QUANTIFIES); self.assertEqual(links[0].target_id.namespace,'EDG')

    def test_evidence_supports_claim_only_when_explicitly_declared(self):
        src=Source(EntityMeta(self.ids.new('SRC'),'source/1.0',1,self.run,self.t,self.actor),'report','R','file://r','a'*64)
        evd=EvidenceSpan(EntityMeta(self.ids.new('EVD'),'evidence/1.0',1,self.run,self.t,self.actor),src.meta.id,'text','p1','b'*64)
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','observational',{},None,opr),),'sources':(src,),'evidence_spans':(evd,)})
        before={x for x in self.registry.state if x.namespace=='EDG'}; self.assertFalse(before)
        rp=self._rp(p,EdgeKind.SUPPORTS,EndpointRefKind.CANONICAL,str(evd.meta.id),EndpointRefKind.TEMP,'tmp-c')
        receipt,result,_=admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertEqual(len(receipt.admitted_edge_ids),1)

    def test_cooccurrence_without_relation_proposal_creates_no_edge(self):
        opr=self.ids.new('OPR'); self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        self.assertFalse([x for x in self.registry.state if x.namespace=='EDG'])

    def test_unknown_temp_ref_fails_closed(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),)})
        rp=self._rp(p,EdgeKind.DERIVED_FROM,EndpointRefKind.TEMP,'missing',EndpointRefKind.TEMP,'tmp-c')
        with self.assertRaisesRegex(ExecutionLinkingError,'unknown temp'):
            admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_invalid_relation_shape_fails_closed(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        rp=self._rp(p,EdgeKind.SUPPORTS,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        with self.assertRaisesRegex(ExecutionLinkingError,'invalid endpoint namespaces'):
            admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_canonical_ref_outside_current_admission_is_rejected(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','observational',{},None,opr),)})
        other=self.ids.new('EVD')
        rp=self._rp(p,EdgeKind.SUPPORTS,EndpointRefKind.CANONICAL,str(other),EndpointRefKind.TEMP,'tmp-c')
        with self.assertRaisesRegex(ExecutionLinkingError,'outside this admission'):
            admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_duplicate_relation_is_rejected_atomically(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        rp1=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c'); rp2=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        with self.assertRaisesRegex(ExecutionLinkingError,'duplicate semantic'):
            admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp1,rp2),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertFalse([x for x in self.registry.state if x.namespace=='EDG'])

    def test_existing_semantic_edge_cannot_be_duplicated_by_second_batch(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        rp1=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp1,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        rp2=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        with self.assertRaisesRegex(ExecutionLinkingError,'already exists'):
            admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp2,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))

    def test_linking_audit_repository_persists_identity_proposal_and_receipt(self):
        opr=self.ids.new('OPR'); p,r,m=self._admit({'claims':(ClaimProposal('tmp-c','x','quantitative',{},None,opr),),'quantities':(QuantityProposal('tmp-q',Decimal('2'),'mm','x',None,opr),)})
        rp=self._rp(p,EdgeKind.QUANTIFIES,EndpointRefKind.TEMP,'tmp-q',EndpointRefKind.TEMP,'tmp-c')
        receipt,_,_=admit_semantic_relations(proposal=p,identity=m,relation_proposals=(rp,),registry=self.registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        conn=sqlite3.connect(':memory:'); repo=ExecutionLinkingAuditRepository(conn); repo.save_identity_map(m); repo.save_relation_proposals((rp,)); repo.save_receipt(receipt)
        view=__import__('researcher_core.r0.sqlite_store',fromlist=['SqliteUnitOfWork']).SqliteUnitOfWork(conn).state_view()
        self.assertEqual(view[str(m.meta.id)]['schema_version'],'admission-identity-map/1.0'); self.assertEqual(view[str(rp.meta.id)]['schema_version'],'semantic-relation-proposal/1.0'); self.assertEqual(view[str(receipt.meta.id)]['schema_version'],'semantic-link-receipt/1.0'); conn.close()

if __name__=='__main__': unittest.main()
