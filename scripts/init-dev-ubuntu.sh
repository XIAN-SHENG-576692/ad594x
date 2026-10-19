#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -r /etc/os-release ]]; then
    echo 'Ubuntu host identification is required.' >&2
    exit 1
fi
if ! (source /etc/os-release; [[ "${ID:-}" == ubuntu ]]); then
    echo 'This bootstrap supports Ubuntu only.' >&2
    exit 1
fi

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
mkdir -p templates/{examples,include,spec,src,tests}
