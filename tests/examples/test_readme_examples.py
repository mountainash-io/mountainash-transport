"""Execute the root README's quick start exactly as written."""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_readme_quickstart_runs(tmp_path: Path, example_environment: dict[str, str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Quick start", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```([^\n]*)\n(.*?)^```\s*$", section, re.MULTILINE | re.DOTALL)
    code = [body for label, body in blocks if label == "python"]
    output = [body for label, body in blocks if label == "text"]
    assert len(code) == 1 and len(output) == 1, "Quick start needs one python and one text block"
    (tmp_path / "quickstart.py").write_text(code[0], encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", "quickstart.py"], cwd=tmp_path,
        env=example_environment, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == output[0].strip()
