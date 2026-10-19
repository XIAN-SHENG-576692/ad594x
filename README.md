# ad594x library generator

A planned clean-slate C library generator for AD594x devices, using Jinja2 for
type-specialized code and separate ACSL contracts. No legacy driver is wrapped
or reused.

**Current stage:** directory scaffold, documentation, bootstrap, and scaffold CI.
No generator, C library, templates, or device support is implemented yet.

On Ubuntu, initialize the workspace with:

```sh
bash scripts/init-dev-ubuntu.sh
bash scripts/check-scaffold.sh
```

Bootstrap installs Python dependencies in `.venv/` and recreates the empty
template directories, which Git cannot preserve. It requires Python 3 with
`venv` and `pip` support.

See [the documentation index](docs/index.md) for architecture, constraints,
planned build and verification commands, and the implementation roadmap.
