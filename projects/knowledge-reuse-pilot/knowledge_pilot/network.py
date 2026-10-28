"""Existing search lifecycle and honest connectivity diagnostics, not bypasses."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from .extract import safe_data
from .lease import FileLease, LeaseBusy
from .paths import checked_output, output_dir


class Network:
    def __init__(self, home, config):
        self.home, self.config = checked_output(home, home), config
        output_dir(self.home / "logs", self.home)
        output_dir(self.home / "state", self.home)

    @staticmethod
    def _json(url, timeout=3):
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))

    def search_health(self):
        try:
            data = self._json(self.config["search_url"].rstrip("/") + "/healthz")
            return {"available": data.get("status") == "ok", "backend": self.config["search_backend"]}
        except Exception as exc:
            return {"available": False, "backend": self.config["search_backend"], "error": f"{type(exc).__name__}: {str(exc)[:180]}"}

    def ensure_search(self):
        health = self.search_health()
        if health["available"]:
            return {**health, "started": False}
        if self.config["search_url"].rstrip("/") != "http://127.0.0.1:8888" or self.config["search_backend"] != "existing-mini-searxng":
            return {**health, "blocked": "no approved launcher for this endpoint"}
        try:
            with FileLease(self.home / "state/search-start.lock", self.home):
                return self._launch_search()
        except LeaseBusy:
            return {**health, "blocked": "start already in progress; no duplicate launch"}

    def _launch_search(self):
        try:
            env = dict(os.environ)
            env.update(TEMP=str(self.home / "tmp"), TMP=str(self.home / "tmp"),
                       TMPDIR=str(self.home / "tmp"), PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8")
            output_dir(self.home / "tmp", self.home)
            launcher = Path(self.config["harness_root"]) / "scripts/tools/start_searxng.py"
            launched = subprocess.run([sys.executable, "-B", str(launcher)], cwd=self.home,
                                      env=env, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=20)
            result = {**self.search_health(), "started": launched.returncode == 0,
                      "launcher_exit": launched.returncode,
                      "launcher_output": (launched.stdout + launched.stderr)[-1200:]}
            self.log("search_start", result)
            return result
        except Exception as exc:
            result = {"available": False, "started": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            self.log("search_start", result)
            return result

    def search(self, query, limit=5):
        ready = self.ensure_search()
        if not ready["available"]:
            return {"status": "blocked", "readiness": ready, "results": []}
        url = self.config["search_url"].rstrip("/") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json", "categories": "general", "limit": max(1, min(int(limit), 10))})
        try:
            data = self._json(url, timeout=75)
            results = data.get("results", [])
            return {"status": "ok" if results else "partial", "backend": self.config["search_backend"], "results": results, "note": "empty results do not prove source absence; backend swallows upstream failures" if not results else ""}
        except Exception as exc:
            return {"status": "blocked", "error": f"{type(exc).__name__}: {str(exc)[:200]}", "results": []}

    def flowsint_health(self):
        try:
            data = self._json(self.config["flowsint_url"].rstrip("/") + "/health")
            return {"available": data.get("status") == "ok", "website_to_text_tested": False,
                    "note": "health is not authentication or enricher execution evidence"}
        except Exception as exc:
            return {"available": False, "status": "BLOCKED_MISSING_SERVICE", "website_to_text_tested": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    def probe_url(self, url):
        import requests
        allowed = {"raw.githubusercontent.com", "github.com", "arxiv.org", "www.flowsint.io", "example.com"}
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in allowed or parsed.username or parsed.password:
            raise ValueError("diagnostic URL is not on the explicit pilot allowlist")
        start = time.monotonic()
        result = {"url": url, "kind": "transport_probe_only_not_flowsint", "proxy_configured": {key: bool(os.environ.get(key)) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")}}
        try:
            with requests.get(url, timeout=8, stream=True, allow_redirects=True) as response:
                body = next(response.iter_content(chunk_size=65536), b"")
                sample = body.decode("utf-8", errors="replace").lower()
                result.update(http_status=response.status_code, content_type=response.headers.get("Content-Type", ""), bytes_sampled=len(body), redirects=[r.status_code for r in response.history], block_page_suspected=any(term in sample for term in ("captcha", "access denied", "verify you are human")))
        except Exception as exc:
            result.update(error_type=type(exc).__name__, error=str(exc)[:200])
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        self.log("transport_probe", result)
        return result

    def log(self, event, result):
        path = checked_output(self.home / "logs/network.jsonl", self.home)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(safe_data({"time": time.time(), "event": event, "result": result}), ensure_ascii=False) + "\n")
