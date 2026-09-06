import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.router.split_claims import split_claims
from scripts.router.resolve_route import resolve
from scripts.router.build_task_plan import build_task_plan


class RouterTests(unittest.TestCase):
    def test_security_beats_requirement(self):
        c = split_claims("сделай аудит безопасности guard")['claims'][0]
        self.assertEqual(c['kind'], 'security')
        self.assertEqual(c['bucket'], 'security')

    def test_review_beats_implementation_on_audit(self):
        r = resolve("проведи аудит кода и исправь слабые места")
        self.assertTrue(r['ok'])
        self.assertEqual(r['route_id'], 'code-review')

    def test_strict_profile_gets_strict_mode(self):
        r = resolve("оптимизируй performance benchmark")
        self.assertEqual(r['profile'], 'strict')
        self.assertEqual(r['execution_mode'], 'worker_reviewer_tester_auditor')

    def test_task_plan_no_hidden_bucket_mismatch(self):
        p = build_task_plan("проведи аудит кода; проверь security guard")
        self.assertIn(p['state'], {'READY','ESCALATED'})
        self.assertIsInstance(p['routing_conflicts'], list)


class FactoryTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(ROOT/'scripts/code-factory/factory_ctl.py'), *args], capture_output=True, text=True)

    def _write(self, td, name, obj):
        p=Path(td)/name; p.write_text(json.dumps(obj),encoding='utf-8'); return str(p)

    def _review(self, verdict='APPROVE'):
        return {'module':'m','verdict':verdict,'comments':[{'file':'x.py','line':1,'problem':'checked','suggestion':'keep or repair','falsification':'run regression tests'}]}

    def _test(self, result='PASS'):
        return {'module':'m','result':result,'passed':3 if result=='PASS' else 2,'failed':0 if result=='PASS' else 1,'coverage':80}

    def _audit(self, verdict='APPROVE'):
        return {'verdict':verdict,'justification':'Independent process audit confirms the gate result is supported.', 'process_analysis':{'contracts_respected':True,'iteration_count':1,'iteration_limit':3,'role_violation':False}}

    def test_reviewer_and_tester_cannot_pass_without_auditor(self):
        with tempfile.TemporaryDirectory() as td:
            state=str(Path(td)/'state.json')
            self.assertEqual(self._run('init','t','task','--state',state).returncode,0)
            self._run('submit','reviewer',self._write(td,'r.json',self._review()),'--state',state)
            r=self._run('submit','tester',self._write(td,'t.json',self._test()),'--state',state)
            out=json.loads(r.stdout)
            self.assertEqual(out['state'],'RUNNING')
            self.assertEqual(out['gate_set']['auditor'],'PENDING')

    def test_all_required_gates_pass_then_finalize(self):
        with tempfile.TemporaryDirectory() as td:
            state=str(Path(td)/'state.json'); self._run('init','t','task','--state',state)
            for role,name,obj in [('reviewer','r.json',self._review()),('tester','t.json',self._test()),('auditor','a.json',self._audit())]:
                r=self._run('submit',role,self._write(td,name,obj),'--state',state)
                self.assertEqual(r.returncode,0,msg=r.stdout+r.stderr)
            self.assertEqual(json.loads(r.stdout)['state'],'PASSED')
            f=self._run('finalize','--state',state)
            self.assertEqual(json.loads(f.stdout)['state'],'DONE')

    def test_retry_creates_fresh_attempt_and_old_failure_does_not_poison(self):
        with tempfile.TemporaryDirectory() as td:
            state=str(Path(td)/'state.json'); self._run('init','t','task','--state',state)
            bad=self._run('submit','reviewer',self._write(td,'bad.json',self._review('REQUEST_CHANGES')),'--state',state)
            out=json.loads(bad.stdout)
            self.assertEqual(out['state'],'RUNNING')
            self.assertEqual(out['attempt'],2)
            self.assertEqual(out['gate_set']['reviewer'],'PENDING')
            for role,name,obj in [('reviewer','r.json',self._review()),('tester','t.json',self._test()),('auditor','a.json',self._audit())]:
                r=self._run('submit',role,self._write(td,name,obj),'--state',state)
            self.assertEqual(json.loads(r.stdout)['state'],'PASSED')

    def test_replay_and_hash_chain_detect_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            state=str(Path(td)/'state.json'); self._run('init','t','task','--state',state)
            rp=self._run('replay','--state',state)
            self.assertEqual(rp.returncode,0)
            self.assertEqual(json.loads(rp.stdout)['integrity_errors'],[])
            data=json.loads(Path(state).read_text(encoding='utf-8'))
            data['events'][0]['payload']['task_name']='tampered'
            Path(state).write_text(json.dumps(data),encoding='utf-8')
            st=self._run('status','--state',state)
            self.assertNotEqual(st.returncode,0)
            self.assertIn('integrity failure',json.loads(st.stdout)['error'])

    def test_attempt_limit_is_enforced_by_reducer(self):
        with tempfile.TemporaryDirectory() as td:
            state=str(Path(td)/'state.json'); self._run('init','t','task','--limit','2','--state',state)
            self._run('submit','tester',self._write(td,'f1.json',self._test('FAIL')),'--state',state)
            r=self._run('submit','tester',self._write(td,'f2.json',self._test('FAIL')),'--state',state)
            out=json.loads(r.stdout)
            self.assertEqual(out['state'],'FAILED')
            self.assertEqual(out['stop_reason'],'attempt_limit')


class RuntimeCompilerTests(unittest.TestCase):
    def test_compiled_snapshot_is_current(self):
        r = subprocess.run([sys.executable, str(ROOT/'scripts/router/compile_runtime.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out['ok'])
        self.assertEqual(len(out['policy_hash']), 64)

    def test_resolver_reports_policy_hash(self):
        r = resolve("проведи аудит кода")
        self.assertTrue(r['snapshot_backed'])
        self.assertEqual(len(r['policy_hash']), 64)

    def test_generated_route_views_have_same_policy_hash(self):
        snap = json.loads((ROOT/'config/runtime_snapshot.json').read_text(encoding='utf-8'))
        for name in ('profile_routes.json','tool_skill_routes.json','skill_to_route_map.json','skills_graph.json'):
            d = json.loads((ROOT/'config'/name).read_text(encoding='utf-8'))
            self.assertTrue(d.get('generated'))
            self.assertEqual(d.get('generated_from_policy_hash'), snap['policy_hash'])


if __name__ == '__main__':
    unittest.main()
