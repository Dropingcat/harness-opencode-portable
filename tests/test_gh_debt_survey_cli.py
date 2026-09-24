"""Тесты CLI gh_debt_survey.sh: полноценные subcommands survey|claim|comment|close|list.

Регресс TD: неверная подкоманда/аргументы раньше создавала файлы-артефакты ('close', 'survey')
и молча писала JSON в файл вместо ошибки. Проверяем: чистый stdout, понятные коды выхода,
отсутствие файлов-артефактов, маскирование токена (unit — с фейковым curl, без сети).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SURVEY = REPO / "scripts" / "tools" / "gh_debt_survey.sh"
API = REPO / "scripts" / "tools" / "gh_debt_api.sh"
FAKE_TOKEN = "ghp_FAKESECRETtoken123"


def run(script, args, cwd, env_extra=None, path_prefix=None):
    env = dict(os.environ)
    env["GH_TOKEN"] = FAKE_TOKEN
    if path_prefix:
        env["PATH"] = path_prefix + os.pathsep + env["PATH"]
    if env_extra:
        env.update(env_extra)
    return subprocess.run([str(script)] + args, cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=60)


class SurveyCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- аргументы и коды выхода (без сети) ---
    def test_no_args_prints_help_nonzero_exit(self):
        r = run(SURVEY, [], self.tmp)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Использование:", r.stdout)
        self.assertNotIn(FAKE_TOKEN, r.stdout + r.stderr)

    def test_unknown_subcommand_fails_without_artifact(self):
        r = run(SURVEY, ["bogus"], self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("неизвестная подкоманда", r.stderr)
        self.assertFalse((self.tmp / "bogus").exists())

    def test_close_wrong_number_reports_type_error(self):
        r = run(SURVEY, ["close", "abc", str(SURVEY)], self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("номер issue", r.stderr)
        self.assertFalse((self.tmp / "close").exists(),
                         "регресс: файл-артефакт 'close' не должен создаваться")

    def test_missing_bodyfile_reports_clearly(self):
        r = run(SURVEY, ["comment", "123", "/nonexistent/file.md"], self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("файл тела не найден", r.stderr)
        self.assertFalse((self.tmp / "comment").exists())

    def test_too_few_args_for_claim(self):
        r = run(SURVEY, ["claim", "only-title"], self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("недостаточно аргументов", r.stderr)

    def test_missing_token_fails_closed(self):
        env = dict(os.environ)
        env.pop("GH_TOKEN", None)
        r = subprocess.run([str(SURVEY), "list"], cwd=str(self.tmp), env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("GH_TOKEN", r.stderr)

    # --- unit c фейковым curl: payload, вывод, маскирование ---
    def _fake_bin(self, resp_file):
        bindir = self.tmp / "bin"
        bindir.mkdir()
        fake = bindir / "curl"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            f"cat {resp_file}\n")
        fake.chmod(0o755)
        return str(bindir)

    def test_claim_success_parses_number(self):
        resp = self.tmp / "resp.json"
        resp.write_text(json.dumps({"number": 42, "html_url": "https://x/y"}))
        body = self.tmp / "body.md"
        body.write_text("test body")
        r = run(SURVEY, ["claim", "T", str(body)], self.tmp,
                path_prefix=self._fake_bin(resp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CLAIMED issue #42", r.stdout)
        self.assertFalse((self.tmp / "claim").exists())

    def test_close_api_error_is_nonzero_and_masked(self):
        resp = self.tmp / "resp.json"
        resp.write_text(json.dumps({"message": f"Bad credentials {FAKE_TOKEN}"}))
        body = self.tmp / "body.md"
        body.write_text("final")
        r = run(SURVEY, ["close", "999", str(body)], self.tmp,
                path_prefix=self._fake_bin(resp))
        self.assertNotEqual(r.returncode, 0)
        combined = r.stdout + r.stderr
        self.assertNotIn(FAKE_TOKEN, combined, "токен не должен попадать в вывод")
        self.assertIn("***TOKEN***", combined)

    def test_comment_success(self):
        resp = self.tmp / "resp.json"
        resp.write_text(json.dumps({"html_url": "https://x/comment"}))
        body = self.tmp / "body.md"
        body.write_text("hello")
        r = run(SURVEY, ["comment", "5", str(body)], self.tmp,
                path_prefix=self._fake_bin(resp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("COMMENT_OK https://x/comment", r.stdout)

    def test_api_cli_wrapper_get(self):
        resp = self.tmp / "resp.json"
        resp.write_text(json.dumps([{"number": 1}]))
        r = run(API, ["GET", "/repos/x/y/issues"], self.tmp,
                path_prefix=self._fake_bin(resp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"number": 1', r.stdout)

    def test_api_cli_usage_without_args(self):
        r = run(API, [], self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Использование:", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
