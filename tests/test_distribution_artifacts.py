from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_check_script_validates_built_artifacts(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist_dir)],
        check=True,
        cwd=ROOT,
    )

    artifacts = sorted(str(path) for path in dist_dir.iterdir())
    assert len(artifacts) == 2

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_dist.py"), *artifacts],
        check=True,
        cwd=ROOT,
    )
