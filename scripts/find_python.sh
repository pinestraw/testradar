#!/usr/bin/env bash
set -euo pipefail

candidates=()
if [[ -n "${PYTHON:-}" ]]; then
  candidates+=("${PYTHON}")
fi
candidates+=(python3.13 python3.12 python3.11 python3.10 python3.9 python3)

for candidate in "${candidates[@]}"; do
  if ! command -v "${candidate}" >/dev/null 2>&1; then
    continue
  fi

  if "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    printf '%s\n' "${candidate}"
    exit 0
  fi
done

echo "Could not find a Python 3.9+ interpreter. Set PYTHON=/path/to/python3.9+." >&2
exit 1
