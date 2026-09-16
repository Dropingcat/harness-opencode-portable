"""Independent canonical-schema regressions; no model or host configuration I/O."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "code-factory"))
import semantic_transport as transport


class CanonicalRetest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = ROOT / "packages" / "opencode-harness-plugin" / "schemas"
        cls.validators = {}
        for kind in ("Request", "Result"):
            schema = json.loads((schemas / f"SemanticExecution{kind}.schema.json").read_text(encoding="utf-8"))
            validator = jsonschema.validators.validator_for(schema)
            validator.check_schema(schema)
            cls.validators[kind] = validator(schema)

    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def request(self, purpose="CODE_WORK", policy=None):
        request = transport.build_coder_request(
            execution_id="independent-retest", purpose=purpose,
            bounded_input={}, expected_output={}, worktree="test-only",
            model_policy=policy, timeout_ms=1)
        self.validators["Request"].validate(request)
        return request

    def check_result(self, request, status, diagnostic):
        original = copy.deepcopy(request)
        result = transport.execute_coder_semantic(request)
        self.validators["Result"].validate(result)
        self.assertEqual(result["runtime_status"], status)
        self.assertIn(diagnostic, result["host_error"])
        self.assertEqual(result["host_session_id"], "unknown")
        self.assertEqual(result["structured_output"], {})
        self.assertIsNone(result["raw_output_ref"])
        self.assertEqual(request, original)
        return result

    def test_non_dict_inputs_are_schema_valid_rejections(self):
        for value in (None, "", "text", [], [1], 0, 42, 3.14, True, False, (), b"x"):
            with self.subTest(value=repr(value)):
                self.check_result(value, "REJECTED_BY_HOST", "BAD_SCHEMA")

    def test_every_required_field_missing_is_schema_valid_rejection(self):
        for field in self.validators["Request"].schema["required"]:
            with self.subTest(field=field):
                request = self.request()
                del request[field]
                self.assertFalse(self.validators["Request"].is_valid(request))
                self.check_result(request, "REJECTED_BY_HOST", "BAD_SCHEMA")

    def test_invalid_field_matrix_is_schema_valid_rejection(self):
        cases = {
            "schema": [None, "wrong"], "execution_id": [None, "", 5],
            "purpose": [None, [], "UNKNOWN"], "contract_schema": [None, ""],
            "parent_host_session_id": [None, ""], "permission_profile": [None, ""],
            "role_ref": [None, []], "bounded_input": [None, []],
            "expected_output": [None, []], "model_policy": [None, "x", []],
            "trace": [None, []], "timeout_ms": [None, True, 0, -1, 1.5, "1"],
            "extra": [1],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    request = self.request()
                    request[field] = value
                    self.assertFalse(self.validators["Request"].is_valid(request))
                    self.check_result(request, "REJECTED_BY_HOST", "BAD_SCHEMA")
        for field in ("provider_id", "model_id", "agent"):
            with self.subTest(model_policy_field=field):
                request = self.request()
                request["model_policy"][field] = None
                self.assertFalse(self.validators["Request"].is_valid(request))
                self.check_result(request, "REJECTED_BY_HOST", "BAD_SCHEMA")

    def test_all_bridge_gate_paths_purposes_and_identity_policies(self):
        peer = ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        self.assertTrue(peer.is_file(), "Bridge-present path must run, not skip")
        environments = (
            {}, {"HARNESS_SEMANTIC_ENABLED": "1"},
            {"OPENCODE_HARNESS_ROOT": str(ROOT)},
            {"HARNESS_SEMANTIC_ENABLED": "0", "OPENCODE_HARNESS_ROOT": str(ROOT)},
            {"HARNESS_SEMANTIC_ENABLED": "1", "OPENCODE_HARNESS_ROOT": str(peer)},
            {"HARNESS_SEMANTIC_ENABLED": "1", "OPENCODE_HARNESS_ROOT": str(ROOT)},
        )
        for index, environment in enumerate(environments):
            for purpose in ("CODE_WORK", "CODE_REVIEW", "CODE_TEST_ANALYSIS"):
                for policy in ({}, {"provider_id": "", "model_id": ""}, {"provider_id": "p", "model_id": "m"}):
                    with self.subTest(environment=index, purpose=purpose, policy=policy):
                        with patch.dict(os.environ, environment, clear=True):
                            bridge = index == len(environments) - 1
                            result = self.check_result(
                                self.request(purpose, policy),
                                "HOST_UNAVAILABLE" if bridge else "REJECTED_BY_HOST",
                                "plugin bridge failed" if bridge else "legacy CLI fallback not allowed")
                            self.assertEqual(result["provider_id"], policy.get("provider_id") or "unknown")
                            self.assertEqual(result["model_id"], policy.get("model_id") or "unknown")
                            self.check_result(None, "REJECTED_BY_HOST", "BAD_SCHEMA")
