#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <python-bin> <pip-install-args...>" >&2
  exit 2
fi

python_bin="$1"
shift

install_log="$(mktemp)"
trap 'rm -f "${install_log}"' EXIT

set +e
"${python_bin}" -m pip install --user "$@" >"${install_log}" 2>&1
status=$?
set -e

if [[ ${status} -eq 0 ]]; then
  cat "${install_log}"
  exit 0
fi

if grep -q "externally-managed-environment" "${install_log}"; then
  echo "pip is externally managed; retrying with --break-system-packages --user" >&2
  "${python_bin}" -m pip install --break-system-packages --user "$@"
  exit 0
fi

cat "${install_log}" >&2
exit "${status}"
