import unittest

from evals.builtins import skill_files_read, skills_used


class SkillEvaluatorsTests(unittest.TestCase):
    def test_skills_used_skips_when_no_skill_tool_calls_are_present(self):
        checks = skills_used(
            client=None,
            project_key="PROJ",
            case={},
            spec={"skills": ["recipes/SKILL.md"]},
            context={"tool_trace": [{"name": "Read", "input": {"file_path": "/tmp/file"}}]},
        )

        self.assertEqual(
            checks,
            [
                {
                    "check": "skills_used",
                    "passed": True,
                    "skipped": True,
                    "message": "skipped: no Skill tool calls in trace (Claude Code only)",
                }
            ],
        )

    def test_skill_files_read_skips_when_no_read_tool_calls_are_present(self):
        checks = skill_files_read(
            client=None,
            project_key="PROJ",
            case={},
            spec={"skills": ["recipes/SKILL.md"]},
            context={"tool_trace": [{"name": "Skill", "input": {"skill": "recipes/SKILL.md"}}]},
        )

        self.assertEqual(
            checks,
            [
                {
                    "check": "skill_files_read",
                    "passed": True,
                    "skipped": True,
                    "message": "skipped: no Read tool calls in trace",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
