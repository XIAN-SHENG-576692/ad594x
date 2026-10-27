# Verification

## Register package checks

Run after [bootstrap](development.md):

```sh
.venv/bin/python scripts/verify_registers.py
```

The checker requires Python/Jinja2, a C11 compiler (`CC`, default `cc`), and
CMake. It uses committed metadata and templates, without network access or the
temporary driver/PDF research files. `--metadata-only` checks metadata without
rendering packages.

The independently implemented checker validates register and field names,
address uniqueness, storage bounds, disjoint fields, unshifted reset and enum
values, field/register reset consistency, source locations, writable masks, and
reserved-mask separation, allowing explicitly recorded legacy/reserved
conflicts. Curated factual anchors reviewed against the allowed
Analog Devices datasheet include ADIID address `0x400`, register and field reset
`0x4144`, and read-only access; these guard against the driver's erroneous zero
reset. Other anchors cover identification, ADC, sequencer, waveform, power, and
clock register resets. These anchors complement exhaustive structural checks;
they do not establish exhaustive independent factual review of every bit.

Generation checks compare the complete expected macro catalog to emitted
macros, including exact `UINT32_C(0xXXXXXXXX)` and `NU` formatting. Every header
compiles independently and with repeated inclusion under strict C11 warnings.
Every macro value is compiled in a static assertion. Examples compile too.
The reviewed driver inventory count (162 registers) is independently anchored.
Default, custom, and empty prefixes render deterministically; invalid prefixes
fail. Manifest file checksums and C template provenance are checked.

Both release archives must be deterministic and contain safe regular-file
paths. Extracted releases are checked in isolation. The prefix template package
renders with its metadata removed and produces the same files as direct
generation for all three prefixes. All prefix cases and the concrete release
build with CMake and run CTest.
Every package contains a comprehensive assertion translation unit rendered from
`templates/tests/registers_assertions.c.j2`, covering every emitted macro.
Malformed path, name-collision, overlapping-field, and overflow inputs must fail
before modifying an existing output directory.

Observed validation on 2026-10-27: repository structure checks, release
generation, and the complete verifier passed with the temporary research
directory unavailable. The frozen inventory contains 22 blocks, 162 registers,
584 fields, 1,223 settings, and 4,087 emitted macros. Four isolated CMake/CTest
builds passed. Independent research-time checks matched all 428 high-level
declaration expressions/locations and every driver-cited canonical field's
position/mask to the permitted driver snapshot.

The setting-ledger check anchors all 428 active high-level driver macro names
with independently extracted hashes of names, raw expressions, and line
locations, checks their disposition
categories, and traces each direct mapping to a same-valued field enumeration
with the original header-line provenance. The final source audit also compared
all 428 raw expressions and line numbers directly with the permitted driver;
none differed. This inventory audit does not by itself prove every API-to-field
interpretation: composite and unresolved settings retain their documented
limitations. The 18 actual C enum selectors are independently anchored as
protocol context or software selectors, with their non-register disposition
preserved. Block-note text and source references must survive metadata import.

PMBW regression anchors cover `SYSHS` position 0, `SYSBW` width 2 at position 2,
50 kHz encoding 1, writable mask `0xD`, and reserved mask `0xFFFFFFF2`.
CALDATLOCK and CLKEN1 register resets remain absent while their allowed sources
conflict. Manifest inventories must exactly match output files, and C artifacts
must identify existing Jinja templates. Reserved-field spelling variants cannot
silently become public fields.

## Evidence limits

Register metadata records reference locations, conflict decisions, and coverage.
A successful offline check establishes those recorded invariants and the
curated anchors. It cannot turn a driver-only field into a datasheet-verified
field or resolve an ambiguity that the allowed references leave open. Unknown
access and missing source detail must remain visible in metadata and package
provenance; zero-valued reset data must have cited evidence.

At that validation, unresolved attributes omitted nine register reset values,
39 writable masks, 42 reserved masks, and 21 field reset values; three field
ranges also lack public position/width/mask constants. The 82 conflict records
and ten driver-only registers remain explicit. Indexed PDF extraction loses
some typography and ECC table column positions; comments preserve that limit,
and ECC decoding is outside this register-only implementation.

The datasheet itself has inconsistencies: the CHIPID aggregate reset is
`0x5502`, while its Revision field table states `0x3`. The driver also assigns
names to clock bits that the datasheet calls reserved. Such discrepancies need
explicit decisions in the metadata rather than silent agreement with generated
output. See the source and coverage notes in the generated packages.

## Future library gates

This implementation is register-only. It does not establish runtime driver,
transport, cppcheck, or formal proof correctness. The planned library gates are
strict compilation, Unity/FFF runtime tests, cppcheck, and Frama-C/WP with
verified external-contract attachment and a false-contract negative control.
Unknown or timed-out proof goals must fail a future proof gate. See
[architecture](architecture.md#contracts) for the contract design.
