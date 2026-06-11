from __future__ import annotations

import argparse
import email
import sys
import tarfile
import zipfile
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from testradar import __version__  # noqa: E402


def _project_urls(metadata: Message) -> dict[str, str]:
    urls: dict[str, str] = {}
    for value in metadata.get_all("Project-URL", []):
        label, _, url = value.partition(",")
        urls[label.strip()] = url.strip()
    return urls


def _assert_common_metadata(metadata: Message) -> None:
    assert metadata["Name"] == "testradar"
    assert metadata["Version"] == __version__
    assert metadata["Requires-Python"] == ">=3.9"
    assert metadata["License-Expression"] == "MIT"
    assert "Typing :: Typed" in metadata.get_all("Classifier", [])
    urls = _project_urls(metadata)
    assert urls["Homepage"] == "https://github.com/pinestraw/testradar"
    assert urls["Documentation"] == "https://github.com/pinestraw/testradar#readme"
    assert urls["Repository"] == "https://github.com/pinestraw/testradar"
    assert urls["Issues"] == "https://github.com/pinestraw/testradar/issues"
    assert urls["Changelog"] == "https://github.com/pinestraw/testradar/releases"
    assert "LICENSE" in metadata.get_all("License-File", [])


def _check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as wheel:
        names = set(wheel.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        assert "testradar/py.typed" in names
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
        metadata = email.message_from_bytes(wheel.read(metadata_name))
        _assert_common_metadata(metadata)
        entry_points = wheel.read(entry_points_name).decode("utf-8")
        assert "[console_scripts]" in entry_points
        assert "testradar = testradar.cli:main" in entry_points
        assert "[pytest11]" in entry_points
        assert "testradar = testradar.pytest_plugin" in entry_points


def _check_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as sdist:
        names = sdist.getnames()
        prefix = names[0].split("/", 1)[0]
        name_set = set(names)
        required = {
            f"{prefix}/LICENSE",
            f"{prefix}/README.md",
            f"{prefix}/pyproject.toml",
            f"{prefix}/docs/releasing.md",
            f"{prefix}/scripts/check_dist.py",
            f"{prefix}/src/testradar/__init__.py",
            f"{prefix}/src/testradar/py.typed",
            f"{prefix}/tests/test_release_metadata.py",
        }
        missing = sorted(required - name_set)
        assert not missing, f"Missing required sdist files: {missing}"
        pkg_info_name = f"{prefix}/PKG-INFO"
        metadata = email.message_from_bytes(sdist.extractfile(pkg_info_name).read())
        _assert_common_metadata(metadata)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate built testradar distributions.")
    parser.add_argument("paths", nargs="*", help="Distribution files to validate. Defaults to dist/*.")
    args = parser.parse_args()

    paths = [Path(value) for value in args.paths] if args.paths else sorted((ROOT / "dist").glob("*"))
    wheels = [path for path in paths if path.suffix == ".whl"]
    sdists = [path for path in paths if path.suffixes[-2:] == [".tar", ".gz"]]

    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(
            f"Expected exactly one wheel and one sdist, got wheels={len(wheels)} sdists={len(sdists)}"
        )

    _check_wheel(wheels[0])
    _check_sdist(sdists[0])
    print(f"Validated distributions: {wheels[0].name}, {sdists[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
