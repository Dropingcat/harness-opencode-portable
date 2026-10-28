"""Task-local composer of agent_loop.run_once and the authenticated V2 CLI API.

This is not a P2 adapter or production capsule implementation. Agent text is
quarantined, never printed or accepted. Token control is observational, as
explicitly authorized by the user; in-flight work can overshoot the threshold.
"""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
WT = ROOT / 'projects/p2-adapter-opencode-v2/guard-recovery/runs/worktree'
ROLES = {'reviewer': ('code-reviewer-runner', 'code-reviewer'),
         'tester': ('code-tester-runner', 'code-tester'),
         'auditor': ('code-auditor-runner', 'code-auditor')}
LIMIT = 100_000
# Original three checks plus the explicitly approved single reviewer retry.
ROLE_LAUNCH_LIMITS = {'reviewer': 2, 'tester': 1, 'auditor': 1}


class Block(Exception):
    pass


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def counted_tokens(info):
    """Conservative sum, including reported cache and reasoning separately."""
    tokens = info.get('tokens')
    if not isinstance(tokens, dict) or not isinstance(tokens.get('cache'), dict):
        raise Block('usage_unavailable')
    fields = [tokens.get(k) for k in ('input', 'output', 'reasoning')]
    fields += [tokens['cache'].get(k) for k in ('read', 'write')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in fields):
        raise Block('usage_invalid')
    return math.ceil(sum(fields))


def model_equal(a, b):
    return (isinstance(a, dict) and isinstance(b, dict)
            and all(a.get(k) == b.get(k) for k in ('id', 'providerID', 'variant'))
            and bool(a.get('id')) and bool(a.get('providerID')))


def check_launch_authorization(ledger, role):
    if role not in ROLE_LAUNCH_LIMITS:
        raise Block('role_not_authorized')
    launched = [job for job in ledger['jobs'] if job.get('launched')]
    if (len(launched) >= sum(ROLE_LAUNCH_LIMITS.values())
            or sum(job['role'] == role for job in launched) >= ROLE_LAUNCH_LIMITS[role]):
        raise Block('launch_limit')


class API:
    def __init__(self, binary):
        self.binary = binary
        self.sequence = 0
        self.owned_ids = set()
        self.deadline = None
        self.run_id = str(time.time_ns())

    def call(self, operation, params=None, body=None, *, cleanup=False):
        self.sequence += 1
        timeout = 2 if cleanup else 6
        if self.deadline is not None and not cleanup:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise Block('job_deadline')
            timeout = min(timeout, remaining)
        with (HERE / 'runs/control-requests.jsonl').open('a', encoding='utf-8') as journal:
            journal.write(json.dumps({'run_id': self.run_id, 'seq': self.sequence,
                                      'operation': operation, 'body_present': body is not None}) + '\n')
        args = [self.binary, 'api', operation]
        for key, value in (params or {}).items():
            args += ['--param', key + '=' + str(value)]
        if body is not None:
            args += ['--data', json.dumps(body, separators=(',', ':'))]
        try:
            proc = subprocess.run(args, capture_output=True, text=True,
                                  encoding='utf-8', timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Block('control_api_timeout') from None
        except OSError:
            raise Block('control_api_unavailable') from None
        if proc.returncode:
            (HERE / 'artifacts/quarantine' / ('api-error-%s-%d.txt' % (self.run_id, self.sequence))).write_text(
                proc.stdout + '\n' + proc.stderr, encoding='utf-8')
            raise Block('control_api_rejected')
        try:
            return json.loads(proc.stdout)
        except ValueError:
            raise Block('control_api_invalid_json') from None

    def info(self, session_id):
        value = self.call('session.get', {'sessionID': session_id}).get('data')
        if not isinstance(value, dict) or value.get('id') != session_id:
            raise Block('session_binding_invalid')
        return value

    def graph(self, root_id, model, expected_agent):
        root = self.info(root_id)
        self.owned_ids.add(root_id)
        if root.get('agent') != expected_agent + '-runner':
            raise Block('primary_role_mismatch')
        pending, nodes = [root], {}
        while pending:
            info = pending.pop()
            sid = info['id']
            if sid in nodes:
                raise Block('session_cycle')
            if not model_equal(info.get('model'), model):
                raise Block('model_binding_mismatch')
            if sid != root_id and info.get('agent') != expected_agent:
                raise Block('specialized_role_mismatch')
            if (info.get('permissions') != root.get('permissions')
                    or info.get('location') != root.get('location')):
                raise Block('child_boundary_mismatch')
            counted_tokens(info)
            nodes[sid] = info
            if len(nodes) > 4:
                raise Block('child_scope_exceeded')
            page = self.call('session.list', {'parentID': sid, 'limit': 20})
            children = page.get('data')
            cursor = page.get('cursor')
            if (not isinstance(children, list) or not isinstance(cursor, dict)
                    or 'next' not in cursor or cursor['next'] is not None):
                raise Block('child_inventory_incomplete')
            for child in children:
                if not isinstance(child, dict) or child.get('parentID') != sid:
                    raise Block('child_ownership_invalid')
                # Record ownership before model/role checks so a refused child
                # is still interrupted, never left running after a mismatch.
                if not isinstance(child.get('id'), str):
                    raise Block('child_id_invalid')
                self.owned_ids.add(child['id'])
                pending.append(child)
        return nodes

    def interrupt(self, ids):
        results = []
        for sid in reversed(ids):
            try:
                value = self.call('session.interrupt', {'sessionID': sid, 'resume': 'false'}, cleanup=True)
                results.append({'session_id': sid, 'response': value})
            except Block as error:
                results.append({'session_id': sid, 'error': str(error)})
        return results


def run(role):
    if role not in ROLES:
        raise Block('role_not_authorized')
    primary, specialized = ROLES[role]
    binary = str(Path(os.environ['APPDATA']) / 'ai.opencode.desktop/cli/2.0.29-x64/opencode-cli.exe')
    if not Path(binary).is_file():
        raise Block('desktop_cli_missing')
    api = API(binary)
    parent = json.loads((HERE / 'runs/parent-metadata.json').read_text(encoding='utf-8'))
    current = api.info(parent['parent_session_id'])
    model = parent['model']
    if not model_equal(current.get('model'), model):
        raise Block('parent_model_changed')
    ledger_path = HERE / 'runs/token-ledger.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'jobs': []}
    if any(job.get('usage_final_unverified') for job in ledger['jobs']):
        raise Block('previous_usage_not_final')
    check_launch_authorization(ledger, role)
    if sum(j['role'] == role for j in ledger['jobs']) >= 4:
        raise Block('precheck_retry_limit')
    spent = sum(job['tokens'] for job in ledger['jobs'])
    if spent >= LIMIT:
        raise Block('token_budget_exhausted')
    capsule = json.loads((HERE / ('contracts/' + role + '.json')).read_text(encoding='utf-8'))
    contract = capsule['prompt']
    report = Path(capsule['output'])
    if report.exists():
        raise Block('output_already_exists')
    created = api.call('session.create', body={
        'title': 'guard-892ecc3-independent-' + role, 'agent': primary,
        'model': model, 'location': {'directory': capsule['workdir']},
        'permissions': capsule['permissions'],
        'metadata': {'task_id': 'guard-independent-gates-20261017', 'role': role}}).get('data')
    if not isinstance(created, dict) or not isinstance(created.get('id'), str):
        raise Block('owned_session_not_created')
    sid = created['id']
    api.owned_ids.add(sid)
    job = {'role': role, 'root_session': sid, 'tokens': 0, 'state': 'STARTED',
           'model': model, 'observational_budget': True, 'launched': False,
           'events_path': 'artifacts/quarantine/' + role + '-events-' + sid + '.json'}
    ledger['jobs'].append(job)
    write_json(ledger_path, ledger)
    if created.get('agent') != primary or not model_equal(created.get('model'), model):
        job['state'] = 'BLOCKED:created_binding_mismatch'
        job['interrupt'] = api.interrupt([sid])
        write_json(ledger_path, ledger)
        return job
    if created.get('permissions') != capsule['permissions']:
        job['state'] = 'BLOCKED:capsule_permissions_not_stored'
        job['interrupt'] = api.interrupt([sid])
        write_json(ledger_path, ledger)
        return job
    try:
        initial = api.graph(sid, model, specialized)
        if len(initial) != 1 or counted_tokens(initial[sid]) != 0:
            raise Block('new_session_not_empty')
        job['native_prechecks'] = []
        for action, resource, expected in [('subagent', specialized, 'allow'),
                                            ('subagent', 'general', 'deny'),
                                            ('edit', str(report), 'allow'),
                                            ('read', '.env', 'deny')]:
            response = api.call('session.permission.create', {'sessionID': sid}, body={
                'action': action, 'resources': [resource], 'save': [], 'agent': primary,
                'metadata': {'diagnostic': 'pre_generation_boundary_check'}})
            observed = response.get('data', {}).get('effect')
            job['native_prechecks'].append({'action': action, 'expected': expected,
                                             'observed': observed})
            if observed != expected:
                raise Block('native_boundary_precheck_failed')
    except Block as error:
        job['state'] = 'BLOCKED:precheck:' + str(error)
        job['interrupt'] = api.interrupt(list(api.owned_ids))
        write_json(ledger_path, ledger)
        return job
    spec = importlib.util.spec_from_file_location('canonical_agent_loop', ROOT / 'scripts/tools/agent_loop.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model_arg = model['providerID'] + '/' + model['id']
    if model.get('variant'):
        model_arg += '#' + model['variant']
    os.environ.update(OPENCODE_BIN=binary, PYTHONIOENCODING='utf-8')
    old_cwd = Path.cwd()
    os.chdir(capsule['workdir'])
    pool = ThreadPoolExecutor(1)
    job['launched'] = True
    write_json(ledger_path, ledger)
    future = pool.submit(module.run_once, primary, model_arg, contract, sid, 90)
    nodes = {sid: created}
    started, block = time.monotonic(), None
    api.deadline = started + 90
    try:
        while not future.done():
            nodes = api.graph(sid, model, specialized)
            job['tokens'] = sum(counted_tokens(info) for info in nodes.values())
            job['observed_sessions'] = list(nodes)
            if spent + job['tokens'] >= LIMIT:
                raise Block('token_budget_reached')
            for owned in nodes:
                pending = api.call('session.permission.list', {'sessionID': owned}).get('data')
                if not isinstance(pending, list):
                    raise Block('permission_inventory_invalid')
                if pending:
                    write_json(HERE / ('runs/' + role + '-permission-requests.json'), pending)
                    raise Block('native_permission_requires_user')
            write_json(ledger_path, ledger)
            if time.monotonic() - started >= 90:
                raise Block('job_deadline')
            time.sleep(1)
        rc, events, returned_sid = future.result()
        write_json(HERE / job['events_path'], events)
        nodes = api.graph(sid, model, specialized)
        job['tokens'] = sum(counted_tokens(info) for info in nodes.values())
        job['observed_sessions'] = list(nodes)
        if returned_sid != sid:
            raise Block('cli_session_binding_mismatch')
        if not any(info.get('agent') == specialized for key, info in nodes.items() if key != sid):
            raise Block('specialized_dispatch_not_observed')
        job.update(exit_code=rc, output_exists=report.is_file(),
                   state='PRODUCED_QUARANTINED' if rc == 0 and report.is_file() else 'BLOCKED:missing_output')
    except (Block, subprocess.TimeoutExpired) as error:
        block = str(error) if isinstance(error, Block) else 'cli_timeout'
        job['state'] = 'BLOCKED:' + block
        job['interrupt'] = api.interrupt(list(api.owned_ids))
    finally:
        if not future.done():
            if 'interrupt' not in job:
                job['interrupt'] = api.interrupt(list(api.owned_ids))
        try:
            _, final_events, _ = future.result(timeout=max(0.1, started + 93 - time.monotonic()))
            write_json(HERE / job['events_path'], final_events)
        except Exception:
            pass
        pool.shutdown(wait=False)
        os.chdir(old_cwd)
        api.deadline = time.monotonic() + 8
        try:
            final_nodes = api.graph(sid, model, specialized)
            job['tokens'] = sum(counted_tokens(info) for info in final_nodes.values())
        except Block:
            job['usage_final_unverified'] = True
        job['elapsed_seconds'] = round(time.monotonic() - started, 2)
        ledger['total_tokens'] = sum(item['tokens'] for item in ledger['jobs'])
        ledger['token_limit'] = LIMIT
        ledger['guard_admission'] = 'NOT_GRANTED'
        write_json(ledger_path, ledger)
    return job


if __name__ == '__main__':
    try:
        result = run(sys.argv[1])
        print(json.dumps({k: result.get(k) for k in ('role', 'state', 'tokens', 'elapsed_seconds', 'output_exists')}))
    except Block as error:
        print(json.dumps({'state': 'BLOCKED', 'reason': str(error)}))
        raise SystemExit(2)
