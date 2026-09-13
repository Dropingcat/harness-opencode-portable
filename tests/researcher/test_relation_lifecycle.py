from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone

from researcher_core.invalidation import DependencyImpactAssessment, ImpactState
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.events import ReasonCode
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.projections import entity_from_event_record, entity_to_event_record
from researcher_core.relation_lifecycle import (
    RelationLifecycleError,
    RelationTransitionRequest,
    project_stale_relations_from_impact,
    transition_relation_state,
)


class Clock:
    def now_ms(self):
        return 1789250000000


class RelationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(52))
        self.actor = ActorRef('AGENT', 'researcher')
        self.t = datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc)
        self.run = self.ids.new('RUN')
        self.evd = self.ids.new('EVD')
        self.claim = self.ids.new('CLM')
        self.edge = GraphEdge(
            self.meta('EDG', 'graph-edge/1.0'),
            self.evd,
            self.claim,
            EdgeKind.SUPPORTS,
            {'provenance_complete': True},
        )

    def meta(self, prefix, schema, revision=1):
        return EntityMeta(self.ids.new(prefix), schema, revision, self.run, self.t, self.actor)

    def impact(self, edge_id):
        return DependencyImpactAssessment(
            self.meta('DIA', 'dependency-impact/1.0'),
            (self.evd,), (), (), (), (edge_id,), ImpactState.STALE_ONLY, None, 2,
        )

    def test_graph_edge_defaults_active_and_event_record_is_backward_compatible(self):
        self.assertEqual(self.edge.state, GraphEdgeState.ACTIVE)
        record = entity_to_event_record(self.edge)
        self.assertEqual(record['entity_record']['state'], 'ACTIVE')
        legacy = {'entity_type': 'GraphEdge', 'entity_record': dict(record['entity_record'])}
        legacy['entity_record'].pop('state')
        rebuilt = entity_from_event_record(legacy)
        self.assertEqual(rebuilt.state, GraphEdgeState.ACTIVE)

    def test_active_to_stale_is_versioned_and_replayable(self):
        result = transition_relation_state(
            self.edge,
            RelationTransitionRequest(self.edge.meta.id, 1, GraphEdgeState.STALE, (ReasonCode('RELATION_PROVENANCE_STALE'),)),
            actor=self.actor,
            event_id=self.ids.new('EVT'),
            timestamp=self.t,
            causation_id=self.ids.new('OPR'),
            correlation_id=self.ids.new('TXN'),
        )
        self.assertEqual(result.edge.state, GraphEdgeState.STALE)
        self.assertEqual(result.edge.meta.revision, 2)
        self.assertEqual(result.event.event_type, 'EDGE_STATE_CHANGED')
        rebuilt = entity_from_event_record(result.event.payload)
        self.assertEqual(rebuilt, result.edge)

    def test_stale_relation_does_not_change_endpoints(self):
        projection = project_stale_relations_from_impact(
            impact=self.impact(self.edge.meta.id),
            graph_edges=(self.edge,),
            expected_revisions={self.edge.meta.id: 1},
            actor=self.actor,
            id_factory=self.ids,
            timestamp=self.t,
            causation_id=self.ids.new('OPR'),
            correlation_id=self.ids.new('TXN'),
        )
        self.assertEqual(len(projection.updated_edges), 1)
        self.assertEqual(projection.updated_edges[0].source_id, self.evd)
        self.assertEqual(projection.updated_edges[0].target_id, self.claim)
        self.assertEqual(projection.updated_edges[0].state, GraphEdgeState.STALE)

    def test_projection_fails_closed_when_canonical_edge_missing(self):
        with self.assertRaisesRegex(RelationLifecycleError, 'not present in canonical graph'):
            project_stale_relations_from_impact(
                impact=self.impact(self.edge.meta.id),
                graph_edges=(), expected_revisions={}, actor=self.actor, id_factory=self.ids,
                timestamp=self.t, causation_id=self.ids.new('OPR'), correlation_id=self.ids.new('TXN'),
            )

    def test_stale_can_be_revalidated_or_terminalized(self):
        stale = transition_relation_state(
            self.edge,
            RelationTransitionRequest(self.edge.meta.id, 1, GraphEdgeState.STALE, (ReasonCode('RELATION_PROVENANCE_STALE'),)),
            actor=self.actor, event_id=self.ids.new('EVT'), timestamp=self.t,
            causation_id=self.ids.new('OPR'), correlation_id=self.ids.new('TXN'),
        ).edge
        active = transition_relation_state(
            stale,
            RelationTransitionRequest(stale.meta.id, 2, GraphEdgeState.ACTIVE, (ReasonCode('RELATION_REVALIDATED'),)),
            actor=self.actor, event_id=self.ids.new('EVT'), timestamp=self.t,
            causation_id=self.ids.new('OPR'), correlation_id=self.ids.new('TXN'),
        ).edge
        self.assertEqual(active.state, GraphEdgeState.ACTIVE)
        self.assertEqual(active.meta.revision, 3)
        invalidated = transition_relation_state(
            stale,
            RelationTransitionRequest(stale.meta.id, 2, GraphEdgeState.INVALIDATED, (ReasonCode('RELATION_INVALIDATED'),)),
            actor=self.actor, event_id=self.ids.new('EVT'), timestamp=self.t,
            causation_id=self.ids.new('OPR'), correlation_id=self.ids.new('TXN'),
        ).edge
        self.assertEqual(invalidated.state, GraphEdgeState.INVALIDATED)

    def test_relation_reason_codes_are_registered(self):
        from pathlib import Path
        from researcher_core.policy import load_policy
        policy = load_policy(Path.cwd())
        self.assertIn('RELATION_PROVENANCE_STALE', policy.reason_codes)
        self.assertIn('RELATION_REVALIDATED', policy.reason_codes)
        self.assertIn('RELATION_INVALIDATED', policy.reason_codes)

    def test_stale_revision_is_rejected(self):
        with self.assertRaisesRegex(RelationLifecycleError, 'revision'):
            transition_relation_state(
                self.edge,
                RelationTransitionRequest(self.edge.meta.id, 2, GraphEdgeState.STALE, (ReasonCode('RELATION_PROVENANCE_STALE'),)),
                actor=self.actor, event_id=self.ids.new('EVT'), timestamp=self.t,
                causation_id=self.ids.new('OPR'), correlation_id=self.ids.new('TXN'),
            )


if __name__ == '__main__':
    unittest.main()
