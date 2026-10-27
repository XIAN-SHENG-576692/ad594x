#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

for required_file in AGENTS.md README.md docs/index.md docs/architecture.md \
    docs/development.md docs/verification.md docs/roadmap.md \
    requirements-dev.txt .github/workflows/ci.yml scripts/generate_registers.py \
    scripts/render_prefix.py templates/include/registers.h.j2 \
    templates/include/registers_block.h.j2 templates/examples/registers_example.c.j2; do
    test -s "$required_file"
done

for directory in examples include release; do
    test -d "templates/$directory"
done
if [[ -n "$(find templates -mindepth 1 -maxdepth 1 \
    ! -name examples ! -name include ! -name spec ! -name src ! -name tests \
    ! -name release \
    -print -quit)" ]]; then
    echo 'Unexpected entry in templates/.' >&2
    exit 1
fi

git check-ignore -q generated/scaffold-probe.c
bash -n scripts/init-dev-ubuntu.sh scripts/check-scaffold.sh
.venv/bin/python -c 'from jinja2 import Environment, StrictUndefined; assert Environment(undefined=StrictUndefined).from_string("{{ value }}").render(value="ready") == "ready"'
.venv/bin/python -m py_compile scripts/generate_registers.py scripts/render_prefix.py
echo 'Repository structure checks passed.'
