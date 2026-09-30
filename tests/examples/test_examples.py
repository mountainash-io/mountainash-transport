"""Execute the recipes users run and check their documented output."""

from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
RECIPES = sorted(EXAMPLES.glob("*/example.py"))
assert RECIPES, "No runnable recipes found"


def _documented_output(recipe: Path) -> str:
    readme = (recipe.parent / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Expected output:\n\n```text\n(.*?)^```", readme, re.MULTILINE | re.DOTALL)
    assert match, f"{recipe.parent.name}/README.md must document its expected output"
    return match.group(1).strip()


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda path: path.parent.name)
def test_recipe_prints_documented_output(
    recipe: Path, tmp_path: Path, example_environment: dict[str, str],
) -> None:
    work = tmp_path / "transport examples"
    shutil.copytree(EXAMPLES, work)
    result = subprocess.run(
        [sys.executable, "-I", str(work / recipe.relative_to(EXAMPLES))], cwd=tmp_path,
        env=example_environment, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == _documented_output(recipe)


def test_index_lists_every_recipe() -> None:
    index = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    missing = [path.parent.name for path in RECIPES if f"]({path.parent.name}/)" not in index]
    assert not missing, f"examples/README.md does not link: {missing}"
