# Development

## Layout

| Path | Purpose |
| --- | --- |
| `templates/{examples,include,spec,src,tests}/` | Example, header, ACSL, implementation, Unity/FFF templates |
| `generated/` | Ignored render output |
| `scripts/` | Bootstrap and validation |
| `.github/workflows/` | Automated checks |

At scaffold stage, `templates/` contains only those five empty directories: no
`.gitkeep`, README, or templates. Git cannot track empty directories; bootstrap
recreates them.

## Bootstrap and current checks

Supported host: Ubuntu with Python 3, pip, and venv. Install prerequisites if
missing, then bootstrap and check from the repository root:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
bash scripts/init-dev-ubuntu.sh
bash scripts/check-scaffold.sh
```

Bootstrap installs `requirements-dev.txt` (Jinja2 and dependencies) from the
configured package index into `.venv/`, leaving system Python unchanged.
CI uses the same bootstrap. Add `init-<PURPOSE>-<HOST>.sh` for other hosts;
do not assume Ubuntu package names there.

## Planned toolchain

Use C11 per [architecture](architecture.md), a host C compiler, CMake/CTest,
Unity, FFF, cppcheck, Frama-C/WP, Why3, and a supported solver. Before
implementation, record compatible versions/revisions, pin CI dependencies, and
verify downloads. No third-party C code is currently vendored.

Planned sequence: render → compile → runtime tests → static analysis → proofs.
Add exact commands when interfaces exist; scaffold checks establish no C
correctness. See [acceptance gates](verification.md#acceptance-gates).

Review templates with rendered validation results; never commit generated output.
