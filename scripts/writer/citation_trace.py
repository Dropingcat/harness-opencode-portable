#!/usr/bin/env python3
"""Conservative literary DOM trace gate, not an independent fact checker."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re

LIMITATIONS = [
    'PASS proves structural/exact-sentence grounding only, not scientific truth.',
    'No semantic paraphrase, causal synthesis, source retrieval or scientific computation.',
    'Evidence quotes are checked against source.text only when supplied; locators are syntactic.',
    'Use one exact claim per sentence with citations before terminal punctuation; headings must match DOM titles.',
]
# Protocol with scripts/researcher/verify_claims.py: when a claim contains digits
# but no measured quantity with a registered unit (grades/marks/service tokens such
# as Р18, Р6М5, ВКС-10, 08Х18Н10Т, AISI1045), the verifier writes an explicit
# documented disposition instead of a fake numeric comparison. The trace gate
# accepts ONLY status NOT_COMPARABLE for this disposition; any substitution of
# status MATCH/PARTIAL_MATCH under this disposition is falsification -> FAIL.
NON_QUANTITY_DISPOSITION = 'non-quantity-grade-token'
MARKER = re.compile(r'\[([^\[\]\n]+)\]')
HEDGE = re.compile(r'^(?:Possibly|Perhaps|Hypothetically|Возможно|Вероятно|Предположительно|По-видимому)[, :]+', re.I)
VERDICTS = {'SUPPORTED', 'CONTRADICTED', 'UNSUPPORTED', 'AMBIGUOUS', 'OPEN'}


class InputError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'duplicate mapping key: {key}')
        result[key] = value
    return result


def load_dom(path):
    raw = Path(path).read_text(encoding='utf-8-sig')
    if Path(path).suffix.lower() == '.json':
        return json.loads(raw, object_pairs_hook=_pairs)
    import yaml
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node):
        return _pairs([(loader.construct_object(k), loader.construct_object(v)) for k, v in node.value])
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return yaml.load(raw, Loader=UniqueLoader)


def _string(value):
    return isinstance(value, str) and bool(value.strip())


def _list(value, where):
    if not isinstance(value, list):
        raise InputError(f'{where} must be list')
    return value


def _index(items, where, seen):
    result = {}
    for item in _list(items, where):
        if not isinstance(item, dict) or not _string(item.get('id')):
            raise InputError(f'{where}: mapping with nonempty string id required')
        key = item['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key) or key in seen:
            raise InputError(f'{where}: invalid/duplicate id {key!r}')
        seen.add(key)
        result[key] = item
    return result


def inventory(dom):
    """Validate typed structure before traversing it; IDs are never coerced."""
    if not isinstance(dom, dict):
        raise InputError('DOM must be mapping')
    seen = set()
    claims = _index(dom.get('claims'), 'claims', seen)
    sources = _index(dom.get('sources'), 'sources', seen)
    structure = dom.get('structure')
    if not isinstance(structure, dict):
        raise InputError('structure must be mapping')
    sections, paragraphs, titles = {}, {}, set()
    for ch in _index(structure.get('chapters'), 'chapters', seen).values():
        if _string(ch.get('title')): titles.add(ch['title'])
        for sid, sec in _index(ch.get('sections'), 'sections', seen).items():
            sections[sid] = sec
            if _string(sec.get('title')): titles.add(sec['title'])
            for pid, p in _index(sec.get('paragraphs'), 'paragraphs', seen).items():
                refs = _list(p.get('claims'), f'{pid}.claims')
                if any(not _string(r) or r not in claims for r in refs) or len(refs) != len(set(refs)):
                    raise InputError(f'{pid}: invalid/dangling claim references')
                if not isinstance(p.get('text'), str):
                    raise InputError(f'{pid}.text must be string')
                paragraphs[pid] = p
    uncertainty = dom.get('uncertainty')
    if not isinstance(uncertainty, dict):
        raise InputError('uncertainty must be mapping')
    for cid, u in uncertainty.items():
        if cid not in claims or not isinstance(u, dict) or u.get('level') not in {'established', 'inferred', 'assumed', 'disputed'} or not isinstance(u.get('note', ''), str):
            raise InputError(f'invalid uncertainty: {cid}')
    for cid, c in claims.items():
        if not _string(c.get('text')) or c.get('kind') not in {'factual', 'derived', 'assumed', 'recommendation'}:
            raise InputError(f'{cid}: invalid claim text/kind')
        v = c.get('verification')
        if not isinstance(v, dict) or v.get('verdict') not in VERDICTS:
            raise InputError(f'{cid}: invalid verification/verdict')
        conf = v.get('confidence')
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise InputError(f'{cid}: confidence must be finite number in [0,1]')
        if cid not in uncertainty:
            raise InputError(f'{cid}: missing uncertainty')
        _list(c.get('evidence'), f'{cid}.evidence')
    for graph in _index(dom.get('graphs', []), 'graphs', seen).values():
        for edge in _list(graph.get('edges'), 'graph.edges'):
            if not isinstance(edge, dict) or not _string(edge.get('relation')) or not _string(edge.get('from')) or not _string(edge.get('to')) or edge['from'] not in claims or edge['to'] not in claims:
                raise InputError('graph edge must resolve to exact claim IDs')
    return claims, sources, sections, paragraphs, titles


def _body(text):
    return re.sub(r'\s+', ' ', text).strip().rstrip('.!?').strip()


def _check(text, dom, issues, checks, strict):
    claims, sources, sections, paragraphs, titles = inventory(dom)
    def issue(kind, detail, severity='high'):
        issues.append({'type': kind, 'severity': severity, 'detail': detail})
    for sid, src in sources.items():
        if not _string(src.get('ref')) or ('text' in src and not isinstance(src['text'], str)):
            issue('malformed_source', sid)
    for cid, c in claims.items():
        ev = c['evidence']
        if not ev: issue('dangling_claim', cid)
        for e in ev:
            if not isinstance(e, dict) or not _string(e.get('source_id')):
                issue('malformed_evidence', cid); continue
            src = sources.get(e['source_id'])
            if src is None: issue('dangling_source', f'{cid}: {e["source_id"]}')
            span = e.get('span')
            quote, locator = e.get('quote'), e.get('locator')
            if span is not None and not isinstance(span, (str, dict)):
                issue('malformed_evidence', f'{cid}: span must be string or mapping')
            if isinstance(span, str):
                m = re.fullmatch(r'(.+?):\s*[«“"](.+)[»”"]', span, re.S)
                if m: locator, quote = m.groups()
                else: issue('malformed_evidence', f'{cid}: span requires locator and exact quoted text')
            elif isinstance(span, dict):
                locator, quote = span.get('locator'), span.get('quote')
            if not _string(locator) or not _string(quote):
                issue('missing_locator_or_quote', cid)
            elif src and isinstance(src.get('text'), str) and quote not in src['text']:
                issue('evidence_quote_mismatch', cid)
            elif src and 'text' not in src:
                checks.append({'name': 'evidence_quote', 'claim_id': cid,
                               'status': 'UNAVAILABLE', 'detail': 'Source body absent; quote/locator syntax only'})
        v = c['verification']
        comp = v.get('numeric_comparison')
        if re.search(r'\d', c['text']) and comp is None:
            issue('numeric_unverified', cid)
        if comp is not None:
            # Numeric conflict policy: a comparison that is not a real match is a
            # conflict UNLESS the verifier explicitly marked the tokens as
            # non-quantity (grade/mark/service tokens) with status NOT_COMPARABLE.
            # For that disposition ONLY NOT_COMPARABLE is legitimate: substituting
            # MATCH/PARTIAL_MATCH (or anything else) under it is falsification.
            if not isinstance(comp, dict) or comp.get('error'):
                issue('numeric_conflict', cid)
            elif comp.get('disposition') == NON_QUANTITY_DISPOSITION:
                if comp.get('status') != 'NOT_COMPARABLE':
                    issue('numeric_conflict', cid)
            elif comp.get('status') not in {'MATCH', 'PARTIAL_MATCH'}:
                issue('numeric_conflict', cid)
        guard = v.get('guard')
        if guard is not None and guard != 'PASS': issue('guard_conflict', cid)
        formula = v.get('formula')
        if formula is not None and (not isinstance(formula, dict) or formula.get('constant_check') != 'formula_consistent'):
            issue('formula_conflict', cid)
        if v.get('error'): issue('verification_error', cid)
        derived = c.get('derived_from', [])
        if isinstance(derived, str): derived = [derived]
        if not isinstance(derived, list) or any(not _string(r) or r not in claims for r in derived):
            issue('dangling_claim', f'{cid}.derived_from')
        elif derived and any(f'[{r}]' not in text for r in derived):
            issue('missing_crossref', cid, 'warning')
    # Exact grounding deliberately rejects arbitrary synthesized or paraphrased sentences.
    count = 0
    for line in text.splitlines():
        if not line.strip(): continue
        if line.lstrip().startswith('#'):
            if line.lstrip('# ').strip() not in titles: issue('orphan_claim', line)
            continue
        for sentence in re.split(r'(?<=[.!?])\s+(?=[^\[])', line.strip()):
            ids = MARKER.findall(sentence)
            cids = [i for i in ids if i in claims]
            sids = [i for i in ids if i in sources]
            for i in ids:
                if i.startswith('§'):
                    if i[1:] not in sections: issue('dangling_section', i)
                elif i not in claims and i not in sources:
                    issue('dangling_claim' if i.startswith('C') else 'dangling_source', i)
            bare = _body(MARKER.sub('', sentence))
            if not bare:
                if cids or sids: issue('orphan_claim', sentence)
                continue
            if len(cids) != 1:
                issue('orphan_claim', sentence); continue
            cid = cids[0]; c = claims[cid]
            local_hedge = HEDGE.match(bare)
            curated_text = _body(c['text'])
            curated_hedge = HEDGE.match(curated_text)
            # A draft may add uncertainty to an unqualified claim, but must not
            # remove or substitute an existing curated epistemic qualifier.
            grounded = HEDGE.sub('', bare) if local_hedge and not curated_hedge else bare
            if grounded != curated_text: issue('unsupported_synthesis', sentence)
            expected = {e.get('source_id') for e in c['evidence'] if isinstance(e, dict)}
            if not sids or any(s not in expected for s in sids): issue('source_mismatch', sentence)
            u = dom['uncertainty'][cid]['level']
            uncertain = c['verification']['verdict'] != 'SUPPORTED' or u != 'established' or c['kind'] == 'assumed'
            if (uncertain or curated_hedge) and not local_hedge:
                issue('masked_uncertainty', sentence)
            count += 1
    checks.append({'name': 'exact_sentence_trace', 'sentences': count, 'claims': len(claims)})
    if not count: issue('orphan_claim', 'No grounded claim sentences')


def run(text, dom, strict=False, fail_on='high'):
    issues, checks = [], []
    try:
        if not _string(text): raise InputError('text must be nonempty string')
        if not isinstance(strict, bool) or fail_on not in {'high', 'warning', 'low'}:
            raise InputError('invalid strict/fail_on')
        _check(text, dom, issues, checks, strict)
    except (InputError, TypeError, ValueError) as exc:
        issues.append({'type': 'malformed_input', 'severity': 'high', 'detail': str(exc)})
    failed = any(i['severity'] == 'high' or strict or fail_on != 'high' for i in issues)
    return {'verdict': 'FAIL' if failed else 'PASS', 'issues': issues, 'checks': checks,
            'scope': 'Deterministic literary DOM traceability; curated metadata is read-only.',
            'limitations': LIMITATIONS}


def error_report(exc):
    return {'verdict': 'FAIL', 'issues': [{'type': 'input_error', 'severity': 'high', 'detail': str(exc)}],
            'checks': [], 'scope': 'Input validation', 'limitations': LIMITATIONS}


def main(argv=None):
    try:
        ap = Parser(description=__doc__)
        ap.add_argument('--text', required=True); ap.add_argument('--dom', required=True)
        ap.add_argument('--strict', action='store_true')
        args = ap.parse_args(argv)
        result = run(Path(args.text).read_text(encoding='utf-8-sig'), load_dom(args.dom), args.strict)
    except Exception as exc:
        result = error_report(exc)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
