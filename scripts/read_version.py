from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "testradar" / "__init__.py"
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def read_version() -> str:
    match = VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not read __version__ from {VERSION_FILE}")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read or validate the testradar package version.")
    parser.add_argument(
        "--check-tag",
        help="Require the supplied git tag, with or without a leading v, to match the package version.",
    )
    args = parser.parse_args()

    version = read_version()
    if args.check_tag is not None:
        tag_version = args.check_tag[1:] if args.check_tag.startswith("v") else args.check_tag
        if tag_version != version:
            print(
                f"Tag version ({args.check_tag}) does not match package version ({version}).",
                file=sys.stderr,
            )
            return 1

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
