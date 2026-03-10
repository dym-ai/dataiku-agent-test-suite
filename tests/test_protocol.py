import json
import sys
import tempfile
import unittest
from pathlib import Path

from suite.protocol import run_agent_command


class RunAgentCommandTests(unittest.TestCase):
    def test_runs_agent_in_provided_cwd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            workspace = temp_path / "workspace"
            workspace.mkdir()
            agent_script = temp_path / "dummy_agent.py"
            marker = workspace / "started_here.txt"

            agent_script.write_text(
                "\n".join(
                    [
                        "import argparse",
                        "import json",
                        "from pathlib import Path",
                        "",
                        "parser = argparse.ArgumentParser()",
                        "parser.add_argument('--request', required=True)",
                        "parser.add_argument('--response', required=True)",
                        "args = parser.parse_args()",
                        "",
                        "request = json.loads(Path(args.request).read_text())",
                        "cwd = Path.cwd()",
                        "marker = cwd / 'started_here.txt'",
                        "marker.write_text(str(cwd))",
                        "response = {",
                        "    'version': 1,",
                        "    'status': 'completed',",
                        "    'summary': f'cwd={cwd}',",
                        "    'stdout': json.dumps({'cwd': str(cwd), 'workspace': request.get('workspace')}),",
                        "    'stderr': ''",
                        "}",
                        "Path(args.response).write_text(json.dumps(response))",
                    ]
                )
                + "\n"
            )

            result = run_agent_command(
                f"{sys.executable} {agent_script}",
                {"workspace": str(workspace)},
                cwd=workspace,
            )

            self.assertEqual(result["status"], "completed")
            self.assertTrue(marker.exists())
            self.assertEqual(Path(marker.read_text()).resolve(), workspace.resolve())
            stdout = json.loads(result["stdout"])
            self.assertEqual(Path(stdout["cwd"]).resolve(), workspace.resolve())
            self.assertEqual(Path(stdout["workspace"]).resolve(), workspace.resolve())


if __name__ == "__main__":
    unittest.main()
