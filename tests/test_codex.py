import unittest

from agents.codex import _extract_codex_stats
from suite.stats import normalize_stats


class CodexStatsExtractionTests(unittest.TestCase):
    def test_extracts_usage_and_tool_counts_from_jsonl(self):
        event_stream = "\n".join(
            [
                '{"type":"item.completed","item":{"id":"item_0","type":"reasoning","text":"thinking"}}',
                '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"working"}}',
                '{"type":"item.completed","item":{"id":"item_2","type":"command_execution","status":"completed"}}',
                '{"type":"item.completed","item":{"id":"item_3","type":"web_search","status":"completed"}}',
                '{"type":"item.completed","item":{"id":"item_4","type":"mcp_tool_call","status":"completed"}}',
                '{"type":"item.completed","item":{"id":"item_5","type":"agent_message","text":"done"}}',
                '{"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":40,"output_tokens":30}}',
            ]
        )

        stats, last_message = _extract_codex_stats(event_stream)

        self.assertEqual(last_message, "done")
        self.assertEqual(
            stats,
            {
                "input_tokens": 120,
                "cached_input_tokens": 40,
                "output_tokens": 30,
                "total_tokens": 150,
                "tool_uses": 3,
                "tool_uses_by_type": {
                    "command_execution": 1,
                    "web_search": 1,
                    "mcp_tool_call": 1,
                },
            },
        )

    def test_ignores_invalid_json_and_non_tool_items(self):
        event_stream = "\n".join(
            [
                "not-json",
                '{"type":"item.completed","item":{"id":"item_0","type":"reasoning","text":"thinking"}}',
                '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"ok"}}',
            ]
        )

        stats, last_message = _extract_codex_stats(event_stream)

        self.assertEqual(stats, {})
        self.assertEqual(last_message, "ok")


class NormalizeStatsTests(unittest.TestCase):
    def test_normalizes_extended_token_fields_and_tool_breakdown(self):
        normalized = normalize_stats(
            {
                "duration_ms": "1234",
                "input_tokens": "100",
                "cached_input_tokens": "25",
                "output_tokens": "20",
                "total_tokens": "120",
                "tool_uses": "3",
                "tool_uses_by_type": {
                    "command_execution": "2",
                    "web_search": 1,
                    "": "4",
                    "bad": "nope",
                },
            }
        )

        self.assertEqual(
            normalized,
            {
                "duration_ms": 1234,
                "input_tokens": 100,
                "cached_input_tokens": 25,
                "output_tokens": 20,
                "total_tokens": 120,
                "tool_uses": 3,
                "tool_uses_by_type": {
                    "command_execution": 2,
                    "web_search": 1,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
