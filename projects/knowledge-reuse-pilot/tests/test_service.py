from types import SimpleNamespace
import unittest

from knowledge_pilot.service import Service


class ServiceTests(unittest.TestCase):
    def test_web_search_does_not_enter_local_table_result_pipeline(self):
        service = Service.__new__(Service)
        service.network = SimpleNamespace(search=lambda *args: {"status": "blocked", "results": []})
        result = service._web({"question": "research question"}, lambda data: None, lambda: False)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["downloader_invoked"])
        self.assertFalse(result["flowsint_invoked"])


if __name__ == "__main__":
    unittest.main()
