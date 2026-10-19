#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

for required_file in AGENTS.md README.md docs/index.md docs/architecture.md \
    docs/development.md docs/verification.md docs/roadmap.md \
    requirements-dev.txt .github/workflows/ci.yml; do
    test -s "$required_file"
done

for directory in examples include spec src tests; do
    test -d "templates/$directory"
    if [[ -n "$(find "templates/$directory" -mindepth 1 -print -quit)" ]]; then
        echo "Expected empty directory: templates/$directory" >&2
        exit 1
    fi
done
if [[ -n "$(find templates -mindepth 1 -maxdepth 1 \
    ! -name examples ! -name include ! -name spec ! -name src ! -name tests \
    -print -quit)" ]]; then
    echo 'Unexpected entry in templates/.' >&2
    exit 1
fi

git check-ignore -q generated/scaffold-probe.c
bash -n scripts/init-dev-ubuntu.sh scripts/check-scaffold.sh
.venv/bin/python -c 'from jinja2 import Environment, StrictUndefined; assert Environment(undefined=StrictUndefined).from_string("{{ value }}").render(value="ready") == "ready"'
echo 'Scaffold checks passed.'
