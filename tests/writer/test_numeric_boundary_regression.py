"""Новые регрессионные тесты кодового контура: numeric-граница (марк-токены)

WR-DISS-CH1-SEC11-PILOT-20261022 · tooling_fix_numeric_2026-10-23 · правка 1–4.

Проверяемый контракт (CODE_FIX_CONTRACT.md Дефект 1 + 2):
  1. Марк-токены (Р18, Р6М5, ВКС-10, 08Х18Н10Т, AISI1045 и т.п.) НЕ считаются
     измеряемыми величинами: verify_claims пишет numeric_comparison
     {status: NOT_COMPARABLE, disposition: non-quantity-grade-token}, и
     citation_trace НЕ выдаёт numeric_conflict/numeric_unverified.
  2. Реальные величины по-прежнему требуют честного сравнения (MATCH/
     PARTIAL_MATCH): NOT_COMPARABLE без disposition (или MISMATCH) -> FAIL.
  3. Falsy-подмена: status MATCH/PARTIAL_MATCH при disposition
     non-quantity-grade-token -> FAIL (фальсификация).
  4. Span-композиция dom_builder: evidence.span := '<locator>: «exact_span»'
     строится штатно из уже присутствующих полей входа (locator + exact_span);
     уже валидные span не трогаются; без exact_span span не выдумывается.

Запуск: python -X utf8 -m unittest tests.writer.test_numeric_boundary_regression -v
"""
import copy
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = Path(os.environ.get('WRITER_CORE_ROOT', ROOT / 'scripts/writer-core'))
WRITER = CORE.parent / 'writer'
sys.path.insert(0, str(WRITER))
sys.path.insert(0, str(CORE))

import citation_trace as trace  # noqa: E402
import sys as _sys
if not hasattr(trace, 'NON_QUANTITY_DISPOSITION'):  # pragma: no cover
    raise AssertionError(
        'resolved wrong citation_trace: ' + getattr(trace, '__file__', '?')
        + ' | path=' + repr(_sys.path[:6]))
from writer_core import dom_builder as db  # noqa: E402

NON_QUANTITY = trace.NON_QUANTITY_DISPOSITION


def fixture():
    """Базовый валидный DOM trace-фикстуры (грейд-токен в claim text)."""
    proposition = 'Установлено, что сталь Р18 после азотирования имеет повышенную твёрдость'
    text = proposition + ' [C-A] [S-A].'
    dom = {'product': {'id': 'SYNTHETIC'},
           'claims': [{'id': 'C-A', 'text': proposition, 'kind': 'factual',
                       'evidence': [{'source_id': 'S-A', 'span': {'locator': 'p.7', 'quote': proposition}}],
                       'verification': {'verdict': 'SUPPORTED', 'confidence': .91,
                                        'provenance': {'curator': 'test-only'}}}],
           'sources': [{'id': 'S-A', 'ref': 'Synthetic source', 'text': proposition}],
           'uncertainty': {'C-A': {'level': 'established', 'note': 'Curated synthetic note'}},
           'structure': {'chapters': [{'id': 'CH-A', 'sections': [{'id': 'SEC-A', 'paragraphs': [
               {'id': 'P-A', 'claims': ['C-A'], 'text': '', 'curated': {'keep': True}},
               {'id': 'P-B', 'claims': [], 'text': 'Protected other paragraph'}]}]}]}}
    return text, dom


class NumericBoundaryRegression(unittest.TestCase):
    def assert_trace(self, text, dom, verdict, strict=False):
        before = copy.deepcopy(dom)
        report = trace.run(text, dom, strict=strict)
        self.assertEqual(before, dom, 'Trace mutated curated metadata')
        self.assertEqual(report['verdict'], verdict, report)
        return report

    def issues(self, text, dom):
        report = trace.run(text, dom)
        return [i['type'] for i in report['issues']]

    # --- 1. Марк-токены не дают numeric_conflict ---------------------------
    def test_mark_token_with_documented_disposition_passes(self):
        text, dom = fixture()
        dom['claims'][0]['verification']['numeric_comparison'] = {
            'status': 'NOT_COMPARABLE',
            'disposition': NON_QUANTITY,
            'reason': 'digits present but no measured quantity with a registered unit',
            'tokens': ['Р18'],
        }
        report = self.assert_trace(text, dom, 'PASS')
        self.assertNotIn('numeric_conflict', [i['type'] for i in report['issues']])
        self.assertNotIn('numeric_unverified', [i['type'] for i in report['issues']])

    def test_mark_token_without_disposition_is_still_conflict(self):
        """Числа есть, comp есть, но без явного disposition — конфликт (не ослабляем)."""
        text, dom = fixture()
        dom['claims'][0]['verification']['numeric_comparison'] = {
            'status': 'NOT_COMPARABLE', 'unit': 'hv'}
        self.assertIn('numeric_conflict', self.issues(text, dom))
        self.assert_trace(text, dom, 'FAIL')

    def test_grade_tokens_like_steel_marks_and_gost(self):
        """Разные классы марк-токенов — все проходят с disposition."""
        for grade in ('Р6М5', 'ВКС-10', '08Х18Н10Т', 'AISI1045', 'ГОСТ 5632-72'):
            with self.subTest(grade=grade):
                text, dom = fixture()
                prop = 'Установлено, что ' + grade + ' применяется после азотирования'
                text = prop + ' [C-A] [S-A].'
                dom['claims'][0]['text'] = prop
                dom['sources'][0]['text'] = prop
                dom['claims'][0]['evidence'][0]['span'] = {'locator': 'p.7', 'quote': prop}
                dom['claims'][0]['verification']['numeric_comparison'] = {
                    'status': 'NOT_COMPARABLE', 'disposition': NON_QUANTITY,
                    'reason': 'mark token', 'tokens': [grade]}
                self.assert_trace(text, dom, 'PASS')

    # --- 2. Реальные величины требуют MATCH/PARTIAL_MATCH ------------------
    def test_real_quantity_requires_match(self):
        text, dom = fixture()
        prop = 'Установлено, что твёрдость слоя составляет 950 HV'
        text = prop + ' [C-A] [S-A].'
        dom['claims'][0]['text'] = prop
        dom['sources'][0]['text'] = prop
        dom['claims'][0]['evidence'][0]['span'] = {'locator': 'p.7', 'quote': prop}
        # MISMATCH -> FAIL
        dom['claims'][0]['verification']['numeric_comparison'] = {'status': 'MISMATCH', 'unit': 'hv'}
        issue_types = self.issues(text, dom)
        self.assertIn('numeric_conflict', issue_types)
        self.assert_trace(text, dom, 'FAIL')
        # MATCH -> PASS
        dom['claims'][0]['verification']['numeric_comparison'] = {'status': 'MATCH', 'unit': 'hv'}
        self.assert_trace(text, dom, 'PASS')
        # PARTIAL_MATCH -> PASS (строгость сохранена)
        dom['claims'][0]['verification']['numeric_comparison'] = {'status': 'PARTIAL_MATCH', 'unit': 'hv'}
        self.assert_trace(text, dom, 'PASS')

    def test_real_quantity_without_comparison_is_unverified(self):
        text, dom = fixture()
        prop = 'Установлено, что твёрдость слоя составляет 950 HV'
        text = prop + ' [C-A] [S-A].'
        dom['claims'][0]['text'] = prop
        dom['sources'][0]['text'] = prop
        dom['claims'][0]['evidence'][0]['span'] = {'locator': 'p.7', 'quote': prop}
        report = trace.run(text, dom)
        self.assertIn('numeric_unverified',
                      [i['type'] for i in report['issues']])
        self.assertEqual(report['verdict'], 'FAIL')

    # --- 3. Falsy-подмена падает -------------------------------------------
    def test_falsy_substitution_match_fails(self):
        text, dom = fixture()
        dom['claims'][0]['verification']['numeric_comparison'] = {
            'status': 'MATCH', 'disposition': NON_QUANTITY,
            'reason': 'fake substitution attempt'}
        report = self.assert_trace(text, dom, 'FAIL')
        self.assertIn('numeric_conflict', [i['type'] for i in report['issues']])

    def test_falsy_substitution_partial_match_fails(self):
        text, dom = fixture()
        dom['claims'][0]['verification']['numeric_comparison'] = {
            'status': 'PARTIAL_MATCH', 'disposition': NON_QUANTITY}
        self.assert_trace(text, dom, 'FAIL')

    def test_falsy_substitution_error_fails(self):
        text, dom = fixture()
        dom['claims'][0]['verification']['numeric_comparison'] = {
            'status': 'MATCH', 'disposition': NON_QUANTITY, 'error': 'fake'}
        self.assert_trace(text, dom, 'FAIL')

    # --- 4. Span-композиция dom_builder -------------------------------------
    def test_compose_evidence_spans_formats_locator_quote(self):
        dom = {'claims': [{'id': 'C-001', 'evidence': [
            {'locator': {'printed_page': 4181, 'lines': [32, 45],
                         'section': '1.Introduction'},
             'exact_span': 'Gas nitriding is a thermochemical surface treatment'},
            {'locator': 'p.7', 'exact_span': 'simple quote'},
            {'locator': {'printed_page': 11}, 'exact_span': 'page only'},
            {'locator': {}, 'exact_span': 'empty locator'},
        ]}]}
        changed = db.compose_evidence_spans(dom)
        self.assertEqual(changed, 4)
        spans = [e['span'] for e in dom['claims'][0]['evidence']]
        self.assertEqual(spans[0],
                         'p4181, lines 32–45, section 1.Introduction: '
                         '«Gas nitriding is a thermochemical surface treatment»')
        self.assertEqual(spans[1], 'p.7: «simple quote»')
        self.assertEqual(spans[2], 'p11: «page only»')
        self.assertEqual(spans[3], 'n/a: «empty locator»')

    def test_compose_evidence_spans_idempotent_and_preserves_valid(self):
        dom = {'claims': [{'id': 'C-001', 'evidence': [
            {'locator': 'p.7', 'exact_span': 'q', 'span': 'p.7: «q»'},
            {'locator': 'p.8', 'exact_span': 'q2', 'span': {'locator': 'p.8', 'quote': 'q2'}},
            {'locator': 'p.9', 'exact_span': 'q3', 'span': 'legacy scalar'},
        ]}]}
        changed = db.compose_evidence_spans(dom)
        self.assertEqual(changed, 1)  # только legacy scalar перекомпонован
        self.assertEqual(dom['claims'][0]['evidence'][0]['span'], 'p.7: «q»')
        self.assertEqual(dom['claims'][0]['evidence'][1]['span']['quote'], 'q2')
        self.assertEqual(dom['claims'][0]['evidence'][2]['span'], 'p.9: «q3»')

    def test_compose_evidence_spans_skips_without_exact_span(self):
        dom = {'claims': [{'id': 'C-001', 'evidence': [
            {'locator': {'printed_page': 1}, 'exact_span': ''},
            {'locator': 'p.2', 'exact_span': None},
            {'locator': 'p.3'},  # нет exact_span вообще
        ]}]}
        changed = db.compose_evidence_spans(dom)
        self.assertEqual(changed, 0)
        for e in dom['claims'][0]['evidence']:
            self.assertNotIn('span', e)

    def test_claims_to_dom_preserves_incoming_evidence(self):
        claims = [{'text': 'claim one', 'qa_status': 'GROUNDED',
                   'evidence': [{'source_id': 'S-001', 'locator': 'p.1',
                                 'exact_span': 'claim one'}]},
                  {'text': 'claim two', 'qa_status': 'PROPOSED'}]
        out = db.claims_to_dom(claims)
        self.assertEqual(len(out[0]['evidence']), 1)
        self.assertEqual(out[0]['evidence'][0]['source_id'], 'S-001')
        self.assertEqual(out[1]['evidence'], [])

    def test_dom_builder_span_composition_after_build(self):
        template = ROOT / 'templates/writer-dom-dissertation.yaml'
        claims = [{'text': 'Установлено, что сталь Р18 применяется',
                   'qa_status': 'GROUNDED',
                   'evidence': [{'source_id': 'S-001',
                                 'locator': {'printed_page': 5, 'lines': [1, 2]},
                                 'exact_span': 'сталь Р18 применяется'}]}]
        dom = db.build_dom(str(template), claims=claims,
                           source_kinds=['published'])
        ev = dom['claims'][0]['evidence']
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]['span'], 'p5, lines 1–2: «сталь Р18 применяется»')
        self.assertTrue(dom['_validation']['valid'], dom['_validation']['errors'])


if __name__ == '__main__':
    unittest.main()