# ad594x register generator

Jinja2 generator for independent AD594x register headers, grouped by datasheet
functional block. Generates concrete headers and a fully expanded prefix-only
template release from one canonical, source-attributed register inventory.

See [docs/index.md](docs/index.md) for scope and task routes;
[setup, generation, release and build commands](docs/development.md) for usage.
This stage contains register definitions only; it implements no device access.
