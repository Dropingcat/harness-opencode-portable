# -*- coding: utf-8 -*-
"""Тесты V2 Debt-Driven Cycle + contracts."""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts', 'meta')))
from contracts import (AcademicParagraph, CatastrophicFailure, DebtSeverity,
                       DebtType, DraftSection, GateResult, SectionDebt, ThreatLevel)
from debt_cycle import DebtDrivenCycle, GateAdapter, ParagraphResolver


def test_contracts_basic():
    p = AcademicParagraph(paragraph_index=0, text='Текст', claims=['C-101'], citations=['C-101'])
    assert p.version == 1
    assert p.model_dump()['claims'] == ['C-101']


def test_draft_is_approved():
    d = DraftSection(section_id='s1', paragraphs=[AcademicParagraph(text='ok')])
    assert d.is_approved is True


def test_draft_critical_debts():
    p = AcademicParagraph(text='x')
    p.debts.append(SectionDebt(paragraph_index=0, severity=DebtSeverity.CRITICAL,
                               description='bad'))
    d = DraftSection(paragraphs=[p])
    assert d.is_approved is False
    assert len(d.critical_debts) == 1


def test_debt_sorted_by_threat():
    d = DraftSection()
    p = AcademicParagraph(text='x')
    p.debts.append(SectionDebt(severity=DebtSeverity.CRITICAL, threat_level=ThreatLevel.L3_STYLE))
    p.debts.append(SectionDebt(severity=DebtSeverity.CRITICAL, threat_level=ThreatLevel.L1_FACTS))
    d.paragraphs = [p]
    sorted_d = d.sorted_debts()
    assert sorted_d[0].threat_level == ThreatLevel.L1_FACTS  # L1 раньше L3


def test_gate_adapter_collects_debts():
    def fake_gate(text, citations, claims):
        r = GateResult()
        r.add('missing_citation', 'нет цитаты', is_critical=True)
        r.add('logic_gap', 'разрыв', is_critical=False)
        return r

    adapter = GateAdapter(fake_gate, 'fake')
    p = AcademicParagraph(text='Текст без цитат', claims=['C-101'], citations=[])
    d = DraftSection(paragraphs=[p])
    adapter(d)
    assert len(p.debts) == 2
    assert p.debts[0].debt_type == DebtType.CITATION_MISSING
    assert p.debts[0].severity == DebtSeverity.CRITICAL
    assert p.debts[1].threat_level == ThreatLevel.L2_LOGIC


def test_cycle_converges_when_fixed():
    # resolver исправляет все критические долги (меняет текст)
    def fix_gate(text, citations, claims):
        r = GateResult()
        if 'FIX' not in text:
            r.add('unverified_claim', 'нужно FIX', is_critical=True)
        return r

    def resolver(draft, debt):
        para = draft.paragraphs[debt.paragraph_index]
        para.text += ' FIX'
        para.citations = ['C-101']
        return draft

    adapter = GateAdapter(fix_gate, 'fix')
    p = AcademicParagraph(text='без фикса')
    d = DraftSection(paragraphs=[p])
    cycle = DebtDrivenCycle(gates=[adapter], resolver=resolver, max_iterations=3)
    result = cycle.run(d)
    assert result.is_approved is True
    assert result.iteration <= 3
    # проверим: долги критичные ушли
    assert len(result.critical_debts) == 0


def test_cycle_stops_at_max_iterations():
    # гейт всегда находит ошибку, resolver не может исправить
    def always_fail(text, citations, claims):
        r = GateResult()
        r.add('logic_gap', 'всегда', is_critical=True)
        return r

    def noop_resolver(draft, debt):
        return draft

    adapter = GateAdapter(always_fail, 'fail')
    p = AcademicParagraph(text='x')
    d = DraftSection(paragraphs=[p])
    cycle = DebtDrivenCycle(gates=[adapter], resolver=noop_resolver, max_iterations=2)
    result = cycle.run(d)
    # не сошёлся, но вернул последний валидный (не упал)
    assert result.iteration == 1  # 0-based: последняя итерация
    assert len(cycle.summary()) >= 3


def test_catastrophic_failure():
    def physics_gate(text, citations, claims):
        raise CatastrophicFailure('физика нарушена')

    adapter = GateAdapter(physics_gate, 'physics')
    p = AcademicParagraph(text='x')
    d = DraftSection(paragraphs=[p])
    cycle = DebtDrivenCycle(gates=[adapter], resolver=lambda dr, dbt: dr, max_iterations=3)
    try:
        cycle.run(d)
        assert False, 'должно быть исключение'
    except CatastrophicFailure:
        assert True


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)