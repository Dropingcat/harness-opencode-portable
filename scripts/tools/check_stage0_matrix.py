#!/usr/bin/env python3
"""Read-only, source-bound stage-0 projection. Generation writes ONLY --output-root.

Default sources are relative to this checkout (thus canonical after deployment).
An exact projection comparison intentionally rejects unsupported additive claims.
No source registry, host setting, or runtime state is ever written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
WS_IDS = ['WS-55A', 'WS-56A', 'WS-56B', 'WS-57A', 'WS-57B', 'WS-58A', 'WS-59A']
RELEVANT_TD = ['TD-004', 'TD-013', 'TD-024', 'TD-053', 'TD-054', 'TD-175',
               'TD-174', 'TD-176', 'TD-177', 'TD-RESTORE-01']
E2E_ORDER = ['E2E-06', 'E2E-02', 'E2E-01', 'E2E-04', 'E2E-03', 'E2E-07', 'E2E-05']
SOURCE_DOCS = ['docs/CODERS/00_INDEX.md', 'docs/CODERS/02_BRANCHES_W1_W13.md',
               'docs/CODERS/03_ACCEPTANCE.md']
EVIDENCE_BASE = 'docs/evidence/tracker-reconciliation-2026-10-14/'
EVIDENCE_PATHS = [EVIDENCE_BASE + p + '.json' for p in [
    'native-verification', 'observer-verification', 'memory-verification',
    'injection-verification', 'encoding-and-bom-probe', 'desktop-runtime',
    'desktop-runtime-2026-10-15']]
DIMENSIONS = ['implemented', 'connected', 'host_tested', 'certified']
OUTPUT = 'config/development_evidence_matrix.json'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique(records):
    result = {}
    for rec in records:
        if rec['id'] in result:
            raise ValueError('duplicate source ID: ' + rec['id'])
        result[rec['id']] = rec
    return result


def stages():
    # Mapping is planning, never an alternate status/closure authority.
    specs = [
        ('baseline', [], ['DEV-02'],
         'Projection has 13 DEV, 7 WS and exact TD inventory; validator and all negative controls pass.'),
        ('guard contracts', [0], ['DEV-08', 'TD-004', 'TD-013', 'TD-RESTORE-01'],
         'Each injection, permission-denial, missing-guard and guard-error case denies execution; zero fail-open outcomes.'),
        ('memory isolation', [0], ['DEV-08', 'TD-175'],
         'Two agent namespaces plus shared scope tested across session switch; zero foreign entries; recurrence, admission and provenance negatives rejected.'),
        ('read-only V2 semantics', [1], ['DEV-03', 'DEV-04', 'DEV-05', 'WS-58A', 'WS-59A', 'TD-053', 'TD-054'],
         'Real V2 read-only model trace plus timeout, cancel, recursion and quota/auth negatives pass; no silent transport or paid fallback.'),
        ('context assembly', [1, 2, 3], ['DEV-08', 'TD-175', 'TD-176', 'TD-177'],
         'Two agent switches show automatic bounded context injection with source IDs; stale and foreign-context negatives rejected.'),
        ('supervision', [4], ['DEV-06', 'TD-024', 'TD-174'],
         'Heartbeat loss and looping child each detected; bounded corrective restart succeeds; durable outbox replay has zero duplicate effects.'),
        ('nested E2E', [5], E2E_ORDER + ['DEV-06'],
         'Seven existing E2E gates run in recorded order with genuine child artifacts and independent negative controls; no fixture-only acceptance.'),
        ('controlled autonomy', [6], ['DEV-09', 'WS-59A', 'TD-RESTORE-01'],
         'Independent real local merge evidence and bounded rollback pass; quota/auth failure pauses; unrelated dirty edits preserved; existing restore debt closure separately authorized.'),
        ('learning last', [7], ['DEV-08'],
         'W8 canon_search positive and absent/stale-source negatives pass before learning; admitted lesson replay is provenance-bound and rejected lesson cannot promote itself.'),
    ]
    return [{'id': f'stage-{i}', 'name': name, 'depends_on': [f'stage-{d}' for d in deps],
             'refs': refs, 'owner': 'code-orchestrator (planning; source TD owners unchanged)',
             'execution': 'NOT_EXECUTED', 'inputs': refs + [f'stage-{d}' for d in deps],
             'outputs': [f'stage-{i} independent acceptance receipt'], 'closure_gates': [gate],
             'prerequisites': ['W8 canon_search verified'] if i == 8 else []}
            for i, (name, deps, refs, gate) in enumerate(specs)]


def build(source_root, tracker_path=None, td_path=None, evidence_root=None):
    source_root = Path(source_root)
    evidence_root = Path(evidence_root or source_root)
    tracker_path = Path(tracker_path or source_root / 'config/development_tracker.json')
    td_path = Path(td_path or source_root / 'config/tech_debt.json')
    tracker, td = load(tracker_path), load(td_path)
    records = tracker['dev_items'] + tracker['workstreams']
    dev = unique(records)
    debts = unique(td['debts'])
    required = {f'DEV-{i:02}' for i in range(1, 14)} | set(WS_IDS)
    if set(dev) != required:
        raise ValueError('tracker coverage must be exactly global 13 DEV + 7 WS')
    if not set(RELEVANT_TD + E2E_ORDER) <= set(debts):
        raise ValueError('required existing TD/E2E ID missing; never synthesize debt IDs')
    counts = {'total': len(debts), 'open': sum(d['status'] == 'open' for d in debts.values()),
              'closed': sum(d['status'] == 'closed' for d in debts.values())}
    if counts != td['counts']:
        raise ValueError('TD declared/actual inventory count drift')
    sources = [{'path': name, 'sha256': digest(path), 'availability': 'AVAILABLE', 'role': role}
               for name, path, role in [
                   ('config/development_tracker.json', tracker_path, 'status authority'),
                   ('config/tech_debt.json', td_path, 'TD status authority')]
               + [(p, source_root / p, 'historical specification, not runtime proof') for p in SOURCE_DOCS]
               + [(p, evidence_root / p, 'durable bounded observation, not semantic certification') for p in EVIDENCE_PATHS]]
    aliases = []
    items = []
    for rec in records:
        external = rec.get('current_readiness', {}).get('external_sources', [])
        for ref in external:
            if ref not in [a['ref'] for a in aliases]:
                alias = ('memory-verification' if 'memory_verification' in ref else
                         'injection-verification' if 'injection_verification' in ref else
                         'desktop-runtime-2026-10-15' if 'runtime_probe' in ref else 'native-verification')
                aliases.append({'ref': ref, 'availability': 'UNRESOLVED_HISTORICAL_PRIVATE_REF',
                                'durable_summary': EVIDENCE_BASE + alias + '.json',
                                'equivalence': 'bounded summary only; not original receipt or certification'})
        readiness = rec.get('current_readiness', {})
        items.append({'id': rec['id'], 'title': rec['title'], 'status': rec['status'],
                      'completion_scope': rec.get('completion_scope', 'Source status retained; no current V2 acceptance inferred'),
                      'readiness': {d: readiness.get(d, 'NOT_TESTED') for d in DIMENSIONS},
                      'readiness_scope': readiness.get('scope', 'No current verified readiness assessment'),
                      'owner': rec.get('owner', 'UNASSIGNED; code-orchestrator coordinates planning'),
                      'source': 'config/development_tracker.json#' + rec['id'],
                      'evidence': [{'provenance': 'tracker reported/historical', 'availability': 'SOURCE_TEXT_ONLY',
                                    'text': rec.get('evidence', ''), 'current_certification': False}],
                      'external_refs': external,
                      'depends_on': [s['id'] for s in stages() if rec['id'] in s['refs']],
                      'closure_gates': [rec.get('next_gate') or rec.get('result') or
                                        'Independent version-scoped receipt and positive/negative tests required'],
                      'queue': 'ADVANCED_SEPARATE' if rec['id'] in ['DEV-07', 'DEV-11', 'DEV-12', 'DEV-13'] else 'BASELINE_PROJECTION'})
    inventory = []
    for rec in td['debts']:
        relevant = rec['id'] in RELEVANT_TD + E2E_ORDER
        inventory.append({'id': rec['id'], 'status': rec['status'], 'title': rec.get('title'),
                          'owner': rec.get('owner') or 'UNASSIGNED',
                          'source_record_sha256': hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                          'assessment': 'SOURCE_BOUND_RELEVANT_NOT_CLOSED' if relevant else 'OUTSIDE_VERIFIED_SCOPE_UNASSESSED',
                          'acceptance': rec.get('acceptance') if relevant else None,
                          'readiness': {d: 'NOT_TESTED' for d in DIMENSIONS},
                          'evidence': 'Registry record only; no new runtime acceptance',
                          'depends_on': [s['id'] for s in stages() if rec['id'] in s['refs']]})
    return {'schema': 'development-stage0-projection/1', 'as_of': '2026-10-15',
            'authority': 'Read-only projection; tracker and TD registry remain sole status authorities',
            'sources': sources, 'inventory_counts': counts, 'items': items, 'td_inventory': inventory,
            'external_aliases': aliases, 'stages': stages(), 'e2e_order': E2E_ORDER,
            'runtime_limits': {'semantic_status': 'NOT_CERTIFIED', 'full_autonomy': 'BLOCKED',
                               'model_driven_native_tool': 'NOT_TESTED', 'quota': 'NOT_TESTED',
                               'auth': 'Active OpenAI OAuth observed, not quota or model execution proof',
                               'activation': 'Canonical E-project only; worktree has no Harness plugin/MCP',
                               'guard_memory': 'Fail-open/enforcement gaps and automatic injection unwired',
                               'p0': 'Input scan PASS plus negative control is not semantic/safety certification'},
            'exclusions': ['No TD closure or new duplicate TD IDs', 'No registry import/sync',
                           'No runtime/memory/daemon/config activation', 'No stages 1-8 execution',
                           'No 182-open-debt audit claim', 'Historical spec-ready is not runtime proof']}


def check(matrix, source_root, tracker_path=None, td_path=None, evidence_root=None):
    try:
        expected = build(source_root, tracker_path, td_path, evidence_root)
        errors = [] if matrix == expected else ['Source-bound projection mismatch (IDs/status/hash/evidence/gates/readiness/dependencies); regenerate and review, never promote by editing projection']
        graph = {s['id']: s['depends_on'] for s in matrix.get('stages', [])}
        visiting, visited = set(), set()

        def visit(node):
            if node not in graph:
                raise ValueError('dangling internal reference: ' + node)
            if node in visiting:
                raise ValueError('dependency cycle: ' + node)
            if node not in visited:
                visiting.add(node)
                for dep in graph[node]:
                    visit(dep)
                visiting.remove(node)
                visited.add(node)
        for node in graph:
            visit(node)
        return errors
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return [str(exc)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--tracker', type=Path)
    parser.add_argument('--td', type=Path)
    parser.add_argument('--evidence-root', type=Path)
    parser.add_argument('--output-root', type=Path, default=ROOT)
    parser.add_argument('--generate', action='store_true', help='Explicitly write projection under output-root only')
    args = parser.parse_args()
    path = args.output_root / OUTPUT
    try:
        params = (args.source_root, args.tracker, args.td, args.evidence_root)
        if args.generate:
            projection = build(*params)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(projection, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        errors = check(load(path), *params)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors = [str(exc)]
    print(json.dumps({'result': 'FAIL' if errors else 'PASS', 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
