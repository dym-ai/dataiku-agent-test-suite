"""Helpers for staging per-run agent workspaces."""

from contextlib import contextmanager
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StagedWorkspace:
    """Details about the staged workspace for one run."""

    source_workspace: Path | None
    run_workspace: Path
    is_copy: bool


@contextmanager
def stage_agent_workspace(agent_workspace=None):
    """Yield a temporary run workspace, optionally copied from a source workspace."""
    with tempfile.TemporaryDirectory(prefix="dataiku-agent-workspace-") as temp_dir:
        temp_root = Path(temp_dir).resolve()

        if agent_workspace is None:
            yield StagedWorkspace(
                source_workspace=None,
                run_workspace=temp_root,
                is_copy=False,
            )
            return

        source_workspace = agent_workspace.resolve()
        run_workspace = temp_root / source_workspace.name
        shutil.copytree(source_workspace, run_workspace)
        yield StagedWorkspace(
            source_workspace=source_workspace,
            run_workspace=run_workspace.resolve(),
            is_copy=True,
        )
