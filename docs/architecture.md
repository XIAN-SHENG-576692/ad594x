# Architecture contract

Design requirements for the [implementation stages](roadmap.md#next-stages).

## Generation

Build a Python/Jinja2 generator independently of the official driver: no
importing, wrapping, or deriving its implementation. Before register access,
record authoritative device register/protocol sources and supported variants
here.

Render every project-authored `.c`, `.h`, and `.acsl` (including examples/tests)
from Jinja2 templates, exclusively into ignored `generated/`. Keep third-party
Unity/FFF external, outside template directories.

Use explicit immutable render configuration, a deterministic file manifest,
`StrictUndefined`, and sorted iteration. Validate before writing; reject path
traversal and name collisions. Identical inputs produce byte-identical output
without timestamps or host paths.

## Naming and specialization

Default prefix: `ad594x`; explicitly empty is valid. Nonempty prefixes must be
portable lower_snake_case identifiers starting with a letter. Reject reserved
identifiers/invalid characters; never silently normalize distinct inputs into
one name. Validate final names against C keywords and collisions, including
with an empty prefix.

Compute `lower_prefix = prefix + "_"` and
`upper_prefix = prefix.upper() + "_"` only when prefix is nonempty; otherwise
both are empty. Apply centrally to all externally visible C names:
functions, typedefs, struct/enum tags, enum constants, macros, callbacks, and
generated filenames. Use lower_snake_case except uppercase macros/constants;
use the same mapping in includes and external ACSL references.

Header guards: `upper_prefix` + uppercase unprefixed header stem + `_H`,
validated as macro names; e.g. `AD594X_DEVICE_H`, empty-prefix `DEVICE_H`.

Generate specializations with Jinja loops/macros, never C11 `_Generic`:

| Suffix | C type |
| --- | --- |
| u8 / i8 | uint8_t / int8_t |
| u16 / i16 | uint16_t / int16_t |
| u32 / i32 | uint32_t / int32_t |
| u64 / i64 | uint64_t / int64_t |
| f32 / f64 | float / double |

Enable specializations only with documented target widths/float representation
and meaningful operations. Every function, including callbacks and hardware
functions, ends in its data type or custom struct name: `ad594x_scale_u16`,
`scale_u16` (empty prefix), `ad594x_plan_device_context` (context output).

## Core and transport

Use explicit immutable input contexts and separate output contexts; no mutable
globals, hidden caches, implicit ownership, or core heap allocation. Return only
error `enum`/`int` or `void`; computed values use output parameters. Prefix every
input parameter `in_`, every output `out_`; make input pointees const where
applicable. Specify pointer validity, aliasing, lifetime, output-on-error, and
overflow per operation. Default: disjoint input/output storage, outputs
unchanged on failure.

Pure functions validate, transform state, encode transactions, and interpret
responses, producing transaction plans and new state through output parameters.
Explicit caller-supplied transport executes plans and feeds observations into
the next transition.
Isolate SPI/GPIO/timing/callback effects there; hardware access is effectful.
Make transport handles and failures explicit.

Prefer generated specialization, bounded buffers, fixed-width arithmetic, and
precomputed constants. Prioritize performance over readability; record measured
tradeoffs and retain defined C behavior. Specify wire byte order; never rely
on packed struct layout or host endianness.

## Contracts

Authoritative ACSL lives in separate `.acsl` files rendered from
`templates/spec/`. Bind contracts to generated functions using the same naming
context. Specify validity/separation, ranges, frame conditions, applicable
termination, success, and errors. Pure logic writes only declared outputs;
model transport effects separately.

Before implementation, demonstrate external-contract attachment to exact
Frama-C translation units; passing a standalone `.acsl` file alone does not
establish attachment. If needed, render an annotated intermediate translation
unit with Jinja2 under `generated/`, keeping separate `.acsl` authoritative.
Validate attachment with the [formal gate](verification.md#acceptance-gates).
