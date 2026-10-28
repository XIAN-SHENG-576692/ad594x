# Development

## Layout

| Path | Purpose |
| --- | --- |
| `data/registers.json` | Canonical inventory, source provenance, conflicts and coverage |
| `templates/include/` | Independent block and umbrella Jinja2 headers |
| `templates/examples/` | Compile-only Jinja2 usage example |
| `templates/release/` | Release documentation and CMake integration |
| `generated/` | Ignored headers, examples, builds, manifests and releases |
| `scripts/` | Bootstrap, import, generation, prefix rendering and verification |

Render all project `.c`, `.h` and future `.acsl` files from Jinja2 into
`generated/` only. `templates/{spec,src,tests}/` are reserved for future work;
no driver implementation or third-party C framework is present.

## Setup

Ubuntu bootstrap:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential cmake
bash scripts/init-dev-ubuntu.sh
```

Other hosts need Python 3, a C11 compiler and CMake; bootstrap checks for Ubuntu.
Create the environment directly:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Requires Jinja2 `>=3.1,<4`; system Python packages stay unchanged.
Evidence updates use permitted driver files and indexed PDF text
([sources](register-evidence.md)); the importer cannot read binary PDFs.
Rendering and release use need no reference downloads.

## Generate, verify and build

Run from the repository root:

```sh
bash scripts/check-scaffold.sh
.venv/bin/python scripts/generate_registers.py --releases
.venv/bin/python scripts/verify_registers.py
cmake -S generated/registers -B generated/build
cmake --build generated/build
ctest --test-dir generated/build --output-on-failure
```

`check-scaffold.sh` checks structure/dependencies; its name is retained for
compatibility. See [verification](verification.md) for generated-artifact
checks and evidence limits.

Choose a custom prefix or explicitly empty prefix:

```sh
.venv/bin/python scripts/generate_registers.py --prefix sensor --output generated/sensor
.venv/bin/python scripts/generate_registers.py --prefix '' --output generated/unprefixed
```

Prefixes: empty or portable lower snake case starting with a letter. Keywords,
invalid/reserved names and final namespace collisions fail without normalization.
Validation precedes output replacement; output must stay under ignored `generated/`.

## Release packages

`--releases` creates independent packages and deterministic `.tar.gz` archives
under `generated/releases/`:

- `ad594x-registers`: complete concrete headers, example and CMake integration.
- `ad594x-registers-prefix-template`: expanded metadata loops, substitutable
  prefix and standalone `scripts/render.py`.

Both include `data/registers.json`, `PROVENANCE.md`, usage docs and a SHA-256
file manifest. Both build outside this checkout with a C11 toolchain;
the prefix package first needs Python/Jinja2 to render.

CI uploads both archives as `register-release-packages` after validation.
Only `v*` tag pushes (e.g. `v1.0.0`) also publish a GitHub Release with those
verified archives and generated notes. Only the publishing job gets
`contents: write`, using the built-in token. Branch/PR/manual runs upload
artifacts only.

```sh
.venv/bin/python generated/releases/ad594x-registers-prefix-template/scripts/render.py --prefix sensor --output generated/release-sensor
cmake -S generated/release-sensor -B generated/release-sensor-build
cmake --build generated/release-sensor-build
ctest --test-dir generated/release-sensor-build --output-on-failure
```

Header comments and inventory define source limits and omitted uncertain constants.
Review templates with rendered verification results; never commit generated output.
Transport/runtime/formal gates remain [future work](roadmap.md).
