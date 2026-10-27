# Architecture contract

Current register-only architecture and requirements for later
[implementation stages](roadmap.md#next-stages).

## Generation

The Python/Jinja2 generator is independent of the official driver: it neither
imports nor wraps driver implementation. `data/registers.json` owns device
scope, the two permitted register references, access dates, per-entry locations,
conflict decisions, and coverage. `scripts/import_registers.py` imports and
reconciles reference metadata; `scripts/generate_registers.py` validates and
renders it without consulting reference files or the network.

Block names occur in header filenames, guards, comments and umbrella includes,
never register/field macro names. Each block header independently includes
`<stdint.h>`. The umbrella includes all blocks. Register macros end in
`REG_ADDR`, `REG_RESET_VALUE`, `WRITABLE_MASK`, or `RESERVED_MASK`; field macros
end in `POSITION`, `WIDTH`, `MASK`, `RESET_VALUE`, or `ENUM_<MEANING>`. All
value macros use hexadecimal `UINT32_C`; positions/widths use unsigned decimal
literals. Field reset/enumeration values are unshifted. Reserved fields have
comments without macros; read-only bits are not reserved. Unresolved constants
are intentionally omitted and explained beside known constants.

The frozen render configuration contains prefix, input path and output path.
Validation covers prefix syntax, final C macro/guard names and global
collisions, file paths, integer ranges, field extents/overlap, and known
register/field reset consistency before writing. Null disputed values are
preserved without publishing a guessed macro. Headers retain all field
descriptions, access, enum meanings, source locations and source disagreements.

Render every project-authored `.c`, `.h`, and `.acsl` (including examples/tests)
from Jinja2 templates, exclusively into ignored `generated/`. Keep third-party
Unity/FFF external, outside template directories.

Use explicit immutable render configuration, a deterministic file manifest,
`StrictUndefined`, and sorted iteration. Validate before writing; reject path
traversal and name collisions. Identical inputs produce byte-identical output
without timestamps or host paths.

`manifest.json` records SHA-256 content hashes and source template paths; it
excludes itself. Release archives normalize ordering, owner, mode, and timestamps,
including the gzip timestamp. The concrete package is ready for a C11 compiler.
The second package materializes every metadata loop into `.j2` files containing
only `lower_prefix`/`upper_prefix` substitutions. Its standalone renderer lives
under `scripts/`, validates final names again, and needs no repository checkout,
temporary references or canonical-inventory processing to render. Both packages
contain the canonical inventory and readable provenance. All build outputs and
archives stay below ignored `generated/`.

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

The remaining sections specify future stages, not current register-only features.

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
Validate attachment with the [formal gate](verification.md#future-library-gates).
