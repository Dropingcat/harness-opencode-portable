import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class WriterRoutingPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pf=ROOT/'.runs'/'test_writer_routing_preflight.json'
        cls.pf.parent.mkdir(parents=True,exist_ok=True)
        r=subprocess.run([sys.executable,'scripts/router/capability_preflight.py'],cwd=ROOT,capture_output=True,text=True,check=True)
        cls.pf.write_text(r.stdout,encoding='utf-8')
    def resolve(self,stage):
        r=subprocess.run([sys.executable,'scripts/router/resolve_bundle.py','написать раздел диссертации по азотированию с референсами','--route-id','writing-prose','--stage',stage,'--preflight',str(self.pf)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr+r.stdout); return json.loads(r.stdout)
    def test_pipeline_stages_are_ready(self):
        for s in ['object-select','reference-prepare','writing-policy','claim-load','draft','semantic-validation','repair','provenance-update']:
            with self.subTest(stage=s): self.assertEqual(self.resolve(s)['bundle_state'],'READY')
    def test_writer_stages_forbid_web(self):
        for s in ['object-select','reference-prepare','writing-policy','draft','semantic-validation','repair','provenance-update']:
            with self.subTest(stage=s): self.assertIn('web.discovery',self.resolve(s)['forbidden_capabilities'])
    def test_semantic_validation_has_validation_plan(self):
        d=self.resolve('semantic-validation'); self.assertIn('validation.plan',d['logical_tools'])

    def test_writing_policy_stage_has_policy_tools(self):
        d=self.resolve('writing-policy'); self.assertIn('writing.policy',d['logical_tools']); self.assertIn('writing.style_instruction',d['logical_tools'])

    def test_draft_stage_has_structured_output_tools(self):
        d=self.resolve('draft'); self.assertIn('draft.artifact',d['logical_tools']); self.assertIn('writer.dispatch',d['logical_tools'])
