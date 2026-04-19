import tempfile
import unittest
from pathlib import Path

from suite.workspaces import stage_agent_workspace


class StageAgentWorkspaceTests(unittest.TestCase):
    def test_creates_empty_temporary_workspace_when_source_not_provided(self):
        with stage_agent_workspace() as staged:
            self.assertIsNone(staged.source_workspace)
            self.assertFalse(staged.is_copy)
            self.assertTrue(staged.run_workspace.exists())
            self.assertEqual(list(staged.run_workspace.iterdir()), [])
            run_workspace = staged.run_workspace

        self.assertFalse(run_workspace.exists())

    def test_copies_source_workspace_into_temporary_run_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_workspace = temp_path / "source"
            source_workspace.mkdir()
            (source_workspace / ".git").mkdir()
            (source_workspace / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
            (source_workspace / "tracked.txt").write_text("source")
            (source_workspace / "subdir").mkdir()
            (source_workspace / "subdir" / "nested.txt").write_text("nested")

            with stage_agent_workspace(source_workspace) as staged:
                self.assertEqual(staged.source_workspace, source_workspace.resolve())
                self.assertTrue(staged.is_copy)
                self.assertNotEqual(staged.run_workspace, source_workspace.resolve())
                self.assertTrue((staged.run_workspace / "tracked.txt").exists())
                self.assertTrue((staged.run_workspace / ".git" / "HEAD").exists())
                self.assertEqual((staged.run_workspace / "subdir" / "nested.txt").read_text(), "nested")

                (staged.run_workspace / "tracked.txt").write_text("modified in run copy")
                run_workspace = staged.run_workspace

            self.assertEqual((source_workspace / "tracked.txt").read_text(), "source")
            self.assertFalse(run_workspace.exists())


if __name__ == "__main__":
    unittest.main()
