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

Every project-authored `.c`, `.h` and future `.acsl` file is rendered from Jinja2
only into `generated/`. Future `templates/{spec,src,tests}/` directories remain
available; no driver implementation or third-party C framework is present.

## Setup

Ubuntu bootstrap:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential cmake
bash scripts/init-dev-ubuntu.sh
```

On another host with Python 3 and a C11 compiler, create a virtual environment
directly; the Ubuntu bootstrap intentionally checks the operating system:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Jinja2 3.1 is required. Evidence updates use the permitted driver files and
indexed PDF text described in [register evidence](register-evidence.md); the
importer does not read binary PDFs. Rendering and release consumption do not
need reference downloads. No system Python packages are changed.

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

The retained `check-scaffold.sh` name is a compatibility entry point for repository
structure/dependency checks. Verification covers actual generated artifacts;
see [verification](verification.md) for evidence and limits.

Choose a custom prefix or explicitly empty prefix:

```sh
.venv/bin/python scripts/generate_registers.py --prefix sensor --output generated/sensor
.venv/bin/python scripts/generate_registers.py --prefix '' --output generated/unprefixed
```

Prefixes must be empty or portable lower snake case starting with a letter.
Keywords, invalid spellings, reserved names and final namespace collisions fail.
Names are never silently normalized. The generator validates before replacing
its output tree, which must be under the repository's ignored `generated/`.

## Release packages

`--releases` creates two independent packages and deterministic `.tar.gz`
archives under `generated/releases/`:

- `ad594x-registers`: complete concrete headers, example and CMake integration.
- `ad594x-registers-prefix-template`: all metadata loops expanded; only the
  prefix remains substitutable, with a standalone `scripts/render.py`.

Both include `data/registers.json`, `PROVENANCE.md`, usage documentation and a
SHA-256 file manifest. The concrete package requires only a C11 toolchain.
The prefix package requires Python/Jinja2 to render, then the same C11 toolchain.
Release builds and prefix rendering work after extraction outside this checkout.

```sh
.venv/bin/python generated/releases/ad594x-registers-prefix-template/scripts/render.py --prefix sensor --output generated/release-sensor
cmake -S generated/release-sensor -B generated/release-sensor-build
cmake --build generated/release-sensor-build
ctest --test-dir generated/release-sensor-build --output-on-failure
```

The header comments and inventory are the authority for source limitations and
deliberately omitted uncertain constants. Review templates together with rendered
verification results; never commit generated output. Transport/runtime/formal
gates remain future work as described in [the roadmap](roadmap.md).
