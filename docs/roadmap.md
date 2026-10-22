# Scope and stages

## Current boundary

Stage 0 covers documentation, ignore rules, bootstrap, and scaffold CI.
Keep [template directories](development.md#layout) empty until a task requests
implementation. The stages below are plans, not standing instructions to execute.

## Next stages

1. Record supported device variants and authoritative register/protocol
   sources. Define render configuration, API/status types, prefix validation,
   and generation manifest per [architecture](architecture.md).
2. Implement generator/templates, starting with pure encoders and state
   transitions; validate naming and applicable type specializations.
3. Add transport adapters, examples, Unity/FFF tests, CMake/CTest, toolchain
   bootstraps, and build/test CI.
4. Attach external ACSL contracts; add cppcheck/Frama-C jobs, enforce
   [acceptance gates](verification.md#acceptance-gates), and measure performance.

Each stage records decisions, executable commands, validation evidence, and
remaining limits in the owning docs per [maintenance](index.md#maintenance).
