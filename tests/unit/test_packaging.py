from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_wheel_contains_package() -> None:
    """Build the wheel and assert it contains medium_mcp/__init__.py."""
    import subprocess

    result = subprocess.run(
        ["python", "-m", "hatchling", "build", "-t", "wheel"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    wheels = list((REPO_ROOT / "dist").glob("*.whl"))
    assert wheels, "no wheel produced"
    with zipfile.ZipFile(wheels[-1]) as zf:
        names = zf.namelist()
    assert any(n.endswith("medium_mcp/__init__.py") for n in names), names
    assert not any(n.startswith("src/") for n in names), names


def test_coverage_floor_is_70() -> None:
    """Coverage floor must start at 70 so Phase 1 can ratchet up."""
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    addopts = pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    assert "--cov-fail-under=70" in addopts
