import random, sqlite3, unittest
from datetime import datetime, timezone
from decimal import Decimal

from researcher_core.execution_admission import compile_local_execution_admission, admit_execution_proposal
from researcher_core.execution_linking import (
    build_admission_identity_map, admit_semantic_relations,
    SemanticRelationProposal, RelationEndpointRef, EndpointRefKind,
)
from researcher_core.ports import CapsuleObservation
from researcher_core.provenance_dependencies import build_knowledge_dependencies
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta, ClaimProposal, QuantityProposal, Source, EvidenceSpan, Claim
from researcher_core.r0.enums import EdgeKind, ClaimStatus
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.registry import InMemoryClaimRegistry, SequenceClock, CycleRandom
from researcher_core.relation_assessment import (
    RelationAssessmentProposal, RelationAssessmentVerdict, RelationUseState,
    MethodMatch, EvidenceQuality, RelationAssessmentError,
    RelationAssessmentAuditRepository, assess_relation, lifecycle_transition_from_assessment, latest_assessment_by_edge,
)
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.task_execution import TaskExecutionResult, TaskExecutionStatus, ExecutionOwner


class Clock:
    def now_ms(self): return 1789258000000


class RelationAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(83))
        self.actor = ActorRef('AGENT','researcher')
        self.t = datetime(2026,9,13,0,30,tzinfo=timezone.utc)
        self.run = self.ids.new('RUN')
        self.card = self.ids.new('RCD')
        self.evd = self.ids.new('EVD')
        self.clm = self.ids.new('CLM')

    def _edge(self, kind=EdgeKind.SUPPORTS, source=None, target=None, state=GraphEdgeState.ACTIVE, revision=1, attrs=None):
        return GraphEdge(
            EntityMeta(self.ids.new('EDG'),'graph-edge/1.0',revision,self.run,self.t,self.actor),
            source or self.evd, target or self.clm, kind, attrs or {}, state,
        )

    def _proposal(self, edge, *, scope='MATCH', direct='DIRECT', method=MethodMatch.MATCH, quality=EvidenceQuality.ADEQUATE):
        return RelationAssessmentProposal(
            EntityMeta(self.ids.new('RAP'),'relation-assessment-proposal/1.0',1,self.run,self.t,self.actor),
            self.card, edge.meta.id, edge.meta.revision, scope, direct, method, quality,
            'typed relation assessment', supporting_refs=(edge.source_id,),
        )

    def test_support_accepted_is_reasoning_eligible_and_edge_stays_active(self):
        edge=self._edge(); assessment,link=assess_relation(edge=edge,proposal=self._proposal(edge),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(assessment.verdict,RelationAssessmentVerdict.ACCEPTED)
        self.assertEqual(assessment.use_state,RelationUseState.ELIGIBLE)
        self.assertEqual(edge.state,GraphEdgeState.ACTIVE)
        self.assertEqual(link.target_id,edge.meta.id)
        self.assertEqual(link.metadata['assessment_id'],str(assessment.meta.id))

    def test_partial_scope_is_qualified(self):
        edge=self._edge(); a,_=assess_relation(edge=edge,proposal=self._proposal(edge,scope='PARTIAL'),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(a.verdict,RelationAssessmentVerdict.QUALIFIED)
        self.assertEqual(a.use_state,RelationUseState.QUALIFIED)

    def test_unknown_signal_is_inconclusive_not_accepted(self):
        edge=self._edge(); a,_=assess_relation(edge=edge,proposal=self._proposal(edge,quality=EvidenceQuality.UNKNOWN),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(a.verdict,RelationAssessmentVerdict.INCONCLUSIVE)
        self.assertEqual(a.use_state,RelationUseState.BLOCKED)

    def test_disjoint_scope_rejects_and_can_invalidate_relation_only(self):
        edge=self._edge(); a,_=assess_relation(edge=edge,proposal=self._proposal(edge,scope='DISJOINT'),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(a.verdict,RelationAssessmentVerdict.REJECTED)
        tr=lifecycle_transition_from_assessment(edge=edge,assessment=a,actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        self.assertIsNotNone(tr); self.assertEqual(tr.edge.state,GraphEdgeState.INVALIDATED)
        self.assertEqual(tr.edge.source_id,edge.source_id); self.assertEqual(tr.edge.target_id,edge.target_id)

    def test_stale_revision_fails_closed(self):
        edge=self._edge(revision=2); p=self._proposal(edge)
        object.__setattr__(p,'expected_edge_revision',1)
        with self.assertRaisesRegex(RelationAssessmentError,'revision'):
            assess_relation(edge=edge,proposal=p,id_factory=self.ids,actor=self.actor,created_at=self.t)

    def test_stale_relation_cannot_be_assessed_as_current(self):
        edge=self._edge(state=GraphEdgeState.STALE)
        with self.assertRaisesRegex(RelationAssessmentError,'ACTIVE'):
            assess_relation(edge=edge,proposal=self._proposal(edge),id_factory=self.ids,actor=self.actor,created_at=self.t)

    def test_quantifies_can_be_accepted_with_explicit_scope(self):
        qty=self.ids.new('QTY'); edge=self._edge(EdgeKind.QUANTIFIES,qty,self.clm)
        a,_=assess_relation(edge=edge,proposal=self._proposal(edge,direct=None),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(a.verdict,RelationAssessmentVerdict.ACCEPTED)

    def test_derived_from_is_explicitly_inconclusive_at_l1(self):
        c2=self.ids.new('CLM'); edge=self._edge(EdgeKind.DERIVED_FROM,c2,self.clm)
        a,_=assess_relation(edge=edge,proposal=self._proposal(edge,direct=None),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(a.verdict,RelationAssessmentVerdict.INCONCLUSIVE)
        self.assertIn('relation:derivation_validator_not_implemented',a.reason_codes)

    def test_strict_dependency_compiler_excludes_unassessed_and_inconclusive_semantic_use(self):
        edge1=self._edge(); edge2=self._edge(target=self.ids.new('CLM'))
        a2,_=assess_relation(edge=edge2,proposal=self._proposal(edge2,quality=EvidenceQuality.UNKNOWN),id_factory=self.ids,actor=self.actor,created_at=self.t)
        build=build_knowledge_dependencies(graph_edges=(edge1,edge2),relation_assessments=(a2,),require_relation_assessment=True,id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        semantic=[d for d in build.dependencies if d.source_id.namespace=='EDG']
        self.assertFalse(semantic)
        self.assertTrue(any(x.startswith('UNASSESSED_EDGE_SEMANTIC_USE_EXCLUDED') for x in build.diagnostics))
        self.assertTrue(any(x.startswith('BLOCKED_EDGE_SEMANTIC_USE_EXCLUDED') for x in build.diagnostics))

    def test_strict_dependency_compiler_includes_accepted_and_qualified_relations(self):
        e1=self._edge(); e2=self._edge(target=self.ids.new('CLM'))
        a1,_=assess_relation(edge=e1,proposal=self._proposal(e1),id_factory=self.ids,actor=self.actor,created_at=self.t)
        a2,_=assess_relation(edge=e2,proposal=self._proposal(e2,scope='PARTIAL'),id_factory=self.ids,actor=self.actor,created_at=self.t)
        build=build_knowledge_dependencies(graph_edges=(e1,e2),relation_assessments=(a1,a2),require_relation_assessment=True,id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        semantic=[d for d in build.dependencies if d.source_id.namespace=='EDG']
        self.assertEqual(len(semantic),2)
        self.assertTrue(all(d.metadata['relation_assessment_id'] for d in semantic))

    def test_latest_assessment_selection_is_deterministic_for_same_edge_revision(self):
        from dataclasses import replace
        from datetime import timedelta
        edge=self._edge(); p1=self._proposal(edge,quality=EvidenceQuality.UNKNOWN); a1,_=assess_relation(edge=edge,proposal=p1,id_factory=self.ids,actor=self.actor,created_at=self.t)
        p2=self._proposal(edge); a2,_=assess_relation(edge=edge,proposal=p2,id_factory=self.ids,actor=self.actor,created_at=self.t+timedelta(seconds=1))
        latest=latest_assessment_by_edge((a2,a1))
        self.assertEqual(latest[edge.meta.id].meta.id,a2.meta.id)
        self.assertEqual(latest[edge.meta.id].verdict,RelationAssessmentVerdict.ACCEPTED)

    def test_assessment_audit_repository_persists_proposal_and_assessment(self):
        edge=self._edge(); p=self._proposal(edge); a,_=assess_relation(edge=edge,proposal=p,id_factory=self.ids,actor=self.actor,created_at=self.t)
        conn=sqlite3.connect(':memory:'); repo=RelationAssessmentAuditRepository(conn); repo.save_proposal(p); repo.save_assessment(a)
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork
        view=SqliteUnitOfWork(conn).state_view()
        self.assertEqual(view[str(p.meta.id)]['schema_version'],'relation-assessment-proposal/1.0')
        self.assertEqual(view[str(a.meta.id)]['verdict'],'ACCEPTED')
        conn.close()

    def test_rejected_relation_is_removed_from_strict_reasoning_after_lifecycle_projection(self):
        edge=self._edge(); a,_=assess_relation(edge=edge,proposal=self._proposal(edge,scope='DISJOINT'),id_factory=self.ids,actor=self.actor,created_at=self.t)
        tr=lifecycle_transition_from_assessment(edge=edge,assessment=a,actor=self.actor,id_factory=self.ids,timestamp=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        build=build_knowledge_dependencies(graph_edges=(tr.edge,),relation_assessments=(a,),require_relation_assessment=True,id_factory=self.ids,actor=self.actor,run_id=self.run,created_at=self.t)
        self.assertFalse([d for d in build.dependencies if d.source_id.namespace=='EDG'])
        self.assertTrue(any(x.startswith('TERMINAL_EDGE_EXCLUDED') for x in build.diagnostics))

    def test_service_artifact_exposes_relation_assessment_separately(self):
        from researcher_core.artifact_builder import build_minimal_service_artifact
        from researcher_core.r0.projections import Snapshot
        edge=self._edge(); p=self._proposal(edge); a,_=assess_relation(edge=edge,proposal=p,id_factory=self.ids,actor=self.actor,created_at=self.t)
        snap=Snapshot(self.ids.new('SNP'), 0, {}, 'fixture')
        artifact=build_minimal_service_artifact(snap,{str(edge.meta.id):edge},'fixture',relation_assessments=(a,))
        row=artifact['relation_assessments'][str(a.meta.id)]
        self.assertEqual(row['edge_id'],str(edge.meta.id)); self.assertEqual(row['verdict'],'ACCEPTED')
        self.assertEqual(artifact['graph_edges'][0]['state'],'ACTIVE')

    def test_full_execution_admission_link_assessment_keeps_claim_open(self):
        req=self.ids.new('RRQ')
        root=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',1,self.run,self.t,self.actor),req,ResearchCardKind.OBJECTIVE,'Objective')
        task=ResearchCard(EntityMeta(self.ids.new('RCD'),'research-card/1.0',3,self.run,self.t,self.actor),req,ResearchCardKind.TASK,'Task',parent_id=root.meta.id,status=ResearchCardStatus.COMPLETED,dimensions={'capability':'fixture'})
        dom=ResearchDOM(EntityMeta(self.ids.new('RDM'),'research-dom/1.0',2,self.run,self.t,self.actor),req,root.meta.id,{root.meta.id:root,task.meta.id:task},())
        registry=InMemoryClaimRegistry(SequenceClock(1789258001000),CycleRandom())
        src=Source(EntityMeta(self.ids.new('SRC'),'source/1.0',1,self.run,self.t,self.actor),'report','R','file://r','a'*64)
        evd=EvidenceSpan(EntityMeta(self.ids.new('EVD'),'evidence/1.0',1,self.run,self.t,self.actor),src.meta.id,'text','p1','b'*64)
        opr=self.ids.new('OPR')
        obs=CapsuleObservation(self.ids.new('OPR'),'fixture','fixture','proposal-observation/1.0',{'claims':(ClaimProposal('tmp-c','x','observational',{},None,opr),),'sources':(src,),'evidence_spans':(evd,)},{'fixture':True})
        ter=TaskExecutionResult(EntityMeta(self.ids.new('TER'),'task-execution-result/1.0',1,self.run,self.t,self.actor),self.ids.new('TEP'),task.meta.id,2,TaskExecutionStatus.SUCCEEDED,ExecutionOwner.RESEARCHER,'fixture',observation=obs)
        eap=compile_local_execution_admission(result=ter,id_factory=self.ids,actor=self.actor,created_at=self.t)
        ear,_,_=admit_execution_proposal(dom=dom,proposal=eap,registry=registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        identity=build_admission_identity_map(proposal=eap,receipt=ear,registry=registry,id_factory=self.ids,actor=self.actor,created_at=self.t)
        srp=SemanticRelationProposal(EntityMeta(self.ids.new('SRP'),'semantic-relation-proposal/1.0',1,self.run,self.t,self.actor),eap.meta.id,RelationEndpointRef(EndpointRefKind.CANONICAL,str(evd.meta.id)),RelationEndpointRef(EndpointRefKind.TEMP,'tmp-c'),EdgeKind.SUPPORTS,'explicit',{'scope_match':'MATCH','directness':'DIRECT'})
        slr,result,_=admit_semantic_relations(proposal=eap,identity=identity,relation_proposals=(srp,),registry=registry,id_factory=self.ids,actor=self.actor,created_at=self.t,causation_id=self.ids.new('OPR'),correlation_id=self.ids.new('TXN'))
        edge=registry.state[result.accepted_ids[0]]
        rap=RelationAssessmentProposal(EntityMeta(self.ids.new('RAP'),'relation-assessment-proposal/1.0',1,self.run,self.t,self.actor),task.meta.id,edge.meta.id,edge.meta.revision,'MATCH','DIRECT',MethodMatch.MATCH,EvidenceQuality.ADEQUATE,'assessment',(evd.meta.id,))
        ras,_=assess_relation(edge=edge,proposal=rap,id_factory=self.ids,actor=self.actor,created_at=self.t)
        claim=next(x for x in registry.state.values() if isinstance(x,Claim))
        self.assertEqual(ras.verdict,RelationAssessmentVerdict.ACCEPTED)
        self.assertEqual(claim.status,ClaimStatus.OPEN)

if __name__=='__main__': unittest.main()
