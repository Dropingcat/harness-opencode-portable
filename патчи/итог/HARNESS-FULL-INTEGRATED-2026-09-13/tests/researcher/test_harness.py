from __future__ import annotations

import unittest

from researcher_core.harness import TraceAuditor, compare_trace_event_types


class HarnessBubbleTests(unittest.TestCase):
    def test_invariant_detects_missing_output_mutation(self) -> None:
        auditor = TraceAuditor().record("input", "case-1", {"value": "x"})

        violations = auditor.require_input_output_pairs()

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].correlation_id, "case-1")

    def test_invariant_accepts_matched_output(self) -> None:
        auditor = TraceAuditor().record("input", "case-1", {}).record("output", "case-1", {})

        self.assertEqual(auditor.require_input_output_pairs(), [])

    def test_payload_snapshot_is_immutable(self) -> None:
        payload = {"items": []}
        auditor = TraceAuditor().record("input", "case-1", payload)
        payload["items"].append("late")

        self.assertEqual(auditor.events[0].payload["items"], ())

    def test_reference_trace_comparison_detects_blind_spot(self) -> None:
        auditor = TraceAuditor().record("input", "case-1", {})

        missing = compare_trace_event_types(auditor.events, ["input", "output"])

        self.assertEqual(missing, {"output"})


if __name__ == "__main__":
    unittest.main()
