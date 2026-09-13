#!/usr/bin/env python3
"""Deterministic R1 planning demo for the BCC lattice example.

No LLM call is made here. The Q/A transcript models PlanningDialectic output;
its extracted card proposals are compiled into ResearchMap + ResearchPatch and
then applied to ResearchDOM.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.research_planning import (
    DecompositionSession,
    PlanningInquiryTurn,
    PlanningRole,
    PlanningTurnKind,
    ResearchCard,
    ResearchCardKind,
    ResearchCardProposal,
    ResearchRequest,
    apply_research_patch,
    compile_decomposition_proposals,
    create_initial_dom,
)


class DemoClock:
    def __init__(self) -> None:
        self._ms = 1_800_000_000_000

    def now_ms(self) -> int:
        self._ms += 1
        return self._ms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    clock = DemoClock()
    ids = EntityIdFactory(clock, random.Random(7))
    actor = ActorRef("AGENT", "researcher")
    run_id = ids.new("RUN")
    created = datetime(2026, 9, 12, 18, 0, tzinfo=UTC)

    def meta(prefix: str, schema: str) -> EntityMeta:
        return EntityMeta(ids.new(prefix), schema, 1, run_id, created, actor)

    request = ResearchRequest(
        meta("RRQ", "research-request/1.0"),
        "Исследовать утверждение: параметр ОЦК-решётки стали уменьшается под действием легирующих элементов",
        {"material_class": "steel", "phase": "bcc_matrix"},
    )
    root = ResearchCard(
        meta("RCD", "research-card/1.0"), request.meta.id, ResearchCardKind.OBJECTIVE,
        "Легирование и изменение параметра ОЦК-решётки",
    )
    dom = create_initial_dom(request, root, ids.new("RDM"))

    q1 = PlanningInquiryTurn(ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION,
                             "Какие независимые направления нужны, чтобы исследовать исходное утверждение?")
    a1 = PlanningInquiryTurn(ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER,
                             "Нужны: параметр решётки и твёрдый раствор; перераспределение элементов по вторичным фазам; микродеформации/напряжения; корректность измерения.",
                             parent_turn_id=q1.id)
    q2 = PlanningInquiryTurn(ids.new("PIT"), PlanningRole.METHODOLOGIST, PlanningTurnKind.QUESTION,
                             "Какие дисциплины и методы позволяют различить эти объяснения?", parent_turn_id=a1.id)
    a2 = PlanningInquiryTurn(ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER,
                             "Физика металлов, физическая металлургия и кристаллография; XRD для a и уширения, TEM/SAED и EDS/EPMA для фаз и распределения состава.",
                             parent_turn_id=q2.id)
    session = DecompositionSession(meta("DCS", "decomposition-session/1.0"), request.meta.id, root.meta.id, (q1, a1, q2, a2))

    proposals = (
        ResearchCardProposal("d1", ResearchCardKind.DIRECTION, "Состав матрицы и параметр ОЦК-решётки", root.meta.id,
                             dimensions={"disciplines": ["physics_of_metals", "crystallography"], "question_types": ["descriptive", "mechanistic", "causal"]}),
        ResearchCardProposal("d1q", ResearchCardKind.QUESTION, "Какие механизмы могут давать уменьшение a?", "d1",
                             dimensions={"question_types": ["mechanistic", "causal"]}),
        ResearchCardProposal("d1m", ResearchCardKind.METHOD_VIEW, "Рентгеновская дифракция", "d1q",
                             dimensions={"methods": ["xrd"]}),
        ResearchCardProposal("d1t", ResearchCardKind.TASK, "Найти зависимости a(c) и проверить альтернативы peak shift", "d1m",
                             dimensions={"capability": "corpus.search"}),

        ResearchCardProposal("d2", ResearchCardKind.DIRECTION, "Перераспределение легирующих элементов во вторичные фазы", root.meta.id,
                             dimensions={"disciplines": ["materials_science", "physical_metallurgy"], "question_types": ["mechanistic", "scope"]}),
        ResearchCardProposal("d2m", ResearchCardKind.METHOD_VIEW, "TEM/SAED + EDS/EPMA", "d2",
                             dimensions={"methods": ["tem", "saed", "eds", "epma"]}),
        ResearchCardProposal("d2t", ResearchCardKind.TASK, "Проверить, остаётся ли легирующий элемент в ОЦК-матрице", "d2m",
                             dimensions={"capability": "document.inspect"}),

        ResearchCardProposal("d3", ResearchCardKind.DIRECTION, "Остаточные напряжения и микродеформации", root.meta.id,
                             dimensions={"disciplines": ["crystallography", "physics_of_metals"], "question_types": ["measurement", "mechanistic"]}),
        ResearchCardProposal("d3t", ResearchCardKind.TASK, "Отделить lattice-parameter shift от strain/broadening effects", "d3",
                             dimensions={"methods": ["xrd"], "capability": "evidence.verify"}),

        ResearchCardProposal("d4", ResearchCardKind.DIRECTION, "Метрологическая корректность определения параметра решётки", root.meta.id,
                             dimensions={"disciplines": ["crystallography", "metrology"], "question_types": ["measurement", "contradiction"]}),
        ResearchCardProposal("d4t", ResearchCardKind.TASK, "Проверить эталон, аппаратную функцию, геометрию и сопоставимость методик", "d4",
                             dimensions={"methods": ["xrd"], "capability": "document.inspect"}),
    )

    compiled = compile_decomposition_proposals(
        session=session, dom=dom, proposals=proposals, id_factory=ids, actor=actor, created_at=created
    )
    reduced = apply_research_patch(
        dom, compiled.patch, actor=actor, id_factory=ids, timestamp=created,
        causation_id=ids.new("OPR"), correlation_id=run_id,
    )

    cards = []
    for card in reduced.dom.cards.values():
        cards.append({
            "id": str(card.meta.id),
            "parent_id": str(card.parent_id) if card.parent_id else None,
            "kind": card.kind.value,
            "title": card.title,
            "status": card.status.value,
            "dimensions": _plain(card.dimensions),
            "created_from": [str(x) for x in card.created_from],
        })
    out = {
        "schema": "research-planning-demo/1.0",
        "objective": request.objective,
        "planning_dialectic": [
            {"id": str(t.id), "role": t.role.value, "kind": t.kind.value, "text": t.text, "parent_turn_id": str(t.parent_turn_id) if t.parent_turn_id else None}
            for t in session.turns
        ],
        "research_map": {key: list(values) for key, values in compiled.research_map.axes.items()},
        "dom_revision": reduced.dom.meta.revision,
        "root_card_id": str(reduced.dom.root_card_id),
        "cards": cards,
        "events": [{"type": e.event_type, "payload": _plain(e.payload)} for e in reduced.events],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


def _plain(value):
    if hasattr(value, "items"):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
