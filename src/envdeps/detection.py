import os
import subprocess
import sys
from pathlib import Path


class DetectEnv:
    """Detect the environment python prefix.

    Methods should be called in the order they are defined to resolve prefix.

    Attributes:
        root: Root directory of project (if `None`, then `venv_dir_in_root` will always return None)
    """

    # NOTE: Referenced https://github.com/tox-dev/pipdeptree/blob/main/src/pipdeptree/_detect_env.py#L50
    # For help.
    def __init__(self, root: Path | None = None) -> None:
        self.root = root

    def venv(self) -> Path | None:
        """Check for standard 'VIRTUAL_ENV' variable (used by stdlib 'venv',
        pyenv, and some others.)"""
        var = os.environ.get("VIRTUAL_ENV")
        if not var:
            return None
        return Path(var)

    def conda(self) -> Path | None:
        """For conda environment."""
        var = os.environ.get("CONDA_PREFIX")
        if not var:
            return None
        return Path(var)

    def pyenv(self) -> Path | None:
        """Pyenv environment should be detected with `venv()`, but this is a
        fallback in case not."""
        var = os.environ.get("PYENV_VIRTUAL_ENV")
        if not var:
            return None
        return Path(var)

    def poetry(self) -> Path | None:
        """Poetry doesn't set an env var like the others, so we will attempt to
        call the CLI for it."""
        try:
            var = subprocess.run(
                ("poetry", "env", "info", "--path"),
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None
        return Path(var.stdout.strip())

    def uv(self) -> Path | None:
        """Should be set for uv managed environments.

        See [Project Environment Path](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path)
        """
        var = os.environ.get("UV_PROJECT_ENVIRONMENT")
        if not var:
            return None
        return Path(var)

    def venv_dir_in_root(self) -> Path | None:
        """Unlike the others, this assumes the env is not active and searches
        for a venv directory in the root of the project."""
        # This, unlike the others, tries to find a venv in the root (if provided)
        if not self.root:
            return None
        pyvenv_cfg = next(self.root.rglob("pyvenv.cfg"), None)
        if not pyvenv_cfg:
            return None
        return pyvenv_cfg.parent

    def fallback_sys_prefix(self) -> Path:
        """This should be the last method tried, it will always return a
        result."""
        return Path(sys.prefix)


def detect_active_env(root: Path | None = None, fallback_sys_prefix: bool = True):
    """Detect the python environment prefix for the given project.

    This looks in several places to attempt to detect the prefix based on strategies of existing package managers/etc.

    Args:
        root: Resolved project root path. If `None`, it will not search for a venv dir in project root.
        fallback_sys_prefix: Fallback to `sys.prefix` if cannot determine prefix from other methods? (Default True)

    Returns:
        prefix: Resolved environment prefix.

    Raises:
        SystemExit: If no environment prefix could be determined.
    """
    detector = DetectEnv(root)
    for detect in [
        detector.venv,
        detector.pyenv,
        detector.conda,
        detector.poetry,
        detector.uv,
        detector.venv_dir_in_root,
        # detector.fallback_sys_prefix,
    ]:
        path = detect()
        if not path:
            continue
        if not path.exists():
            continue
        return path
    if fallback_sys_prefix:
        return detector.fallback_sys_prefix()
    print("Unable to detect virtual environment.", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    prefix = detect_active_env()
    print(prefix)
