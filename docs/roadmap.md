# Scope and handoff

## Stage 0: this commit

- Create documentation, ignore rules, host bootstrap, and scaffold CI.
- Leave `templates/` and its five subdirectories free of files.
- Provide architecture and verification contracts for later sessions.
- Commit the reviewed scaffold and stop; do not start generator implementation.

## Later stages (not authorized by this scaffold task)

1. Record device variants and authoritative register/protocol sources. Define
   immutable render configuration, API/status types, prefix validation, and
   a deterministic generation manifest.
2. Implement the Jinja2 generator and templates, starting with pure encoders
   and state transitions. Validate default/custom/empty naming and every
   applicable primitive/custom type specialization.
3. Add transport adapters, generated examples and Unity/FFF tests, CMake/CTest,
   toolchain bootstrap scripts, and build/test CI jobs.
4. Attach separate ACSL contracts to generated functions, add cppcheck and
   Frama-C jobs, enforce verification acceptance gates, and measure performance.

Each later stage must update `docs/` with decisions, executable commands,
validation evidence, and remaining limits. Do not expand `AGENTS.md` with logs
or implementation guidance.
