"""``examples/`` runs as shipped (PLAN.md 5.3): the script and the command line."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from archlux.cli import main

EXAMPLES = Path(__file__).parents[2] / "examples"


def test_the_example_script_legalizes_every_plan(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(EXAMPLES / "legalize_examples.py"), run_name="__main__")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert all("valid=True" in line for line in lines)


@pytest.mark.parametrize("name", ["t2", "t3_load_bearing", "generated"])
def test_the_command_line_legalizes_every_example(name: str, tmp_path: Path) -> None:
    out = tmp_path / "fixed.json"
    plan = str(EXAMPLES / f"{name}.json")
    assert main(["verify", plan, "--min-width", "0.9"]) == 1
    assert main(["legalize", plan, "--tiling", "--min-width", "0.9", "-o", str(out)]) == 0
    assert main(["verify", str(out), "--min-width", "0.9"]) == 0
