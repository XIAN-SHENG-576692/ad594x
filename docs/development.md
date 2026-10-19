# Development

## Layout

| Path | Purpose |
| --- | --- |
| `templates/examples/` | Future example templates |
| `templates/include/` | Future public header templates |
| `templates/spec/` | Future separate ACSL contract templates |
| `templates/src/` | Future implementation templates |
| `templates/tests/` | Future Unity/FFF test templates |
| `generated/` | Ignored generated output; absent until generation exists |
| `scripts/` | Host setup and scaffold validation |
| `docs/` | All detailed project context and decisions |
| `.github/workflows/` | Automated checks |

At this stage `templates/` contains only the five listed empty directories.
Do not add `.gitkeep`, README files, or templates there. Git stores files, not
empty directories; bootstrap recreates them on each checkout.

## Bootstrap and current checks

Supported bootstrap host: Ubuntu with Python 3, pip, and venv installed.
If needed, install prerequisites with the host package manager:

```sh
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
bash scripts/init-dev-ubuntu.sh
bash scripts/check-scaffold.sh
```

The script may download Jinja2 and its dependencies from the configured Python
package index. It uses `.venv/` and does not change system Python. CI invokes
this same bootstrap. Other hosts need a dedicated `init-<PURPOSE>-<HOST>.sh`
script when support is added; do not silently assume Ubuntu package names.

## Planned toolchain

Adopt C11 without `_Generic`, a host C compiler, CMake/CTest, Unity, FFF,
cppcheck, Frama-C/WP, Why3, and a supported proof solver. Select and record
compatible versions and dependency revisions before implementation. Pin CI
dependencies and verify downloads then; no third-party C code is vendored now.

The future build sequence is render, compile, runtime test, static analysis,
and formal verification. Exact generator/CMake/Frama-C commands are deliberately
unavailable until those interfaces exist. Do not describe planned commands as
working or treat the scaffold check as evidence that a C library is correct.

Before changes, read architecture and roadmap. Update detailed decisions here
under `docs/`; keep root `AGENTS.md` as routing only. Keep generated output out
of commits and review templates together with their rendered validation results.
