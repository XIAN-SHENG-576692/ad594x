# Architecture contract

Status: design requirements; no implementation exists in this stage.

## Generation boundary

Implement a new Python generator using Jinja2; do not import, wrap, or derive
implementation from the official driver. Independently establish register and
protocol facts from device documentation in a later stage, recording sources
and supported device variants here before implementing register access.

All project-authored `.c`, `.h`, and `.acsl` artifacts, including examples and
tests, must come from Jinja2 templates. Third-party Unity/FFF dependencies stay
external; do not copy their sources into project template directories.
Write results exclusively beneath ignored `generated/`.

Use an explicit immutable render configuration, a deterministic file manifest,
Jinja `StrictUndefined`, and sorted iteration. Validate configuration before
writing; reject output path traversal and name collisions. Identical inputs
must produce byte-identical results without timestamps or host paths.

## Naming and specialization

Default prefix: `ad594x`; accept an explicitly empty prefix. For nonempty
prefixes, accept a portable lower_snake_case identifier beginning with a letter;
reject reserved identifiers and invalid characters rather than silently mapping
distinct inputs to one name. Validate resulting names against C keywords and
collisions, including the empty-prefix case.

Compute `lower_prefix = prefix + "_"` and
`upper_prefix = prefix.upper() + "_"` only when prefix is nonempty; otherwise
both are empty. Apply these centrally to all externally visible C names:
functions, typedefs, struct/enum tags, enum constants, macros, callbacks, and
generated filenames. Use lower_snake_case except uppercase macros/constants.
Include directives and external ACSL references must use the same mapping.

Generate specializations with Jinja loops/macros, never C11 `_Generic`:

| Suffix | C type |
| --- | --- |
| u8 / i8 | uint8_t / int8_t |
| u16 / i16 | uint16_t / int16_t |
| u32 / i32 | uint32_t / int32_t |
| u64 / i64 | uint64_t / int64_t |
| f32 / f64 | float / double |

Require the target's documented widths and floating representation before
enabling corresponding specializations. A function ends in its data type or
custom struct name; e.g. `ad594x_scale_u16`, `scale_u16` with an empty prefix,
or `ad594x_plan_device_context` for a context-producing operation. Apply this
rule to callbacks and hardware-facing functions as well. Avoid unsupported
specializations rather than inventing meaningless operations for every type.

## Functional C core and hardware boundary

Use explicit immutable input contexts and separate output contexts. No mutable
globals, hidden caches, implicit ownership, or core heap allocation. Functions
return only an error `enum`/`int` or `void`; all computed values leave through
output parameters. Every input parameter starts `in_`; every output parameter
starts `out_`. Input pointees are const where applicable. Define pointer
validity, aliasing, lifetime, output-on-error, and overflow rules per operation;
default to disjoint input/output storage and unchanged outputs on failure.
All generated headers use `#pragma once`.

Pure functions validate, transform state, encode transactions, and interpret
responses. Actual SPI, GPIO, timing, and callbacks necessarily have effects:
isolate them in an explicit caller-supplied transport boundary. The pure core
returns transaction plans and a new state; the transport executes the plans
and passes observations into the next pure transition. Do not claim hardware
access itself is side-effect-free. Transport handles and failures are explicit.

Prefer generated specialization, bounded buffers, fixed-width arithmetic,
and precomputed constants. Performance takes precedence over readability;
record measured tradeoffs and retain defined C behavior. Specify wire byte
order explicitly; never depend on packed struct layout or host endianness.

## Contract ownership

Keep ACSL exclusively in generated `.acsl` files rendered from `templates/spec/`.
Bind each contract to its generated C function using the same naming context.
Specify validity/separation, ranges, frame conditions, termination where
applicable, success semantics, and error behavior. Pure logic permits writes
only to declared outputs. Model transport effects separately.

Before implementation, demonstrate the selected Frama-C mechanism for attaching
external contracts to exact translation units. Do not assume a standalone ACSL
file is automatically applied by passing it to Frama-C. If attachment requires
an intermediate annotated translation unit, generate it with Jinja2 under
`generated/` and keep the authoritative contracts in separate `.acsl` files.
