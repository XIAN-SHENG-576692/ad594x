# Register evidence and unresolved attributes

The register package supports AD5940 and AD5941. Canonical, offline metadata is
[data/registers.json](../data/registers.json). Its evidence comes exclusively from
[the ADI no-OS AD5940 directory](https://github.com/analogdevicesinc/no-OS/tree/main/drivers/afe/ad5940)
and [the AD5940/AD5941 Rev. G data sheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad5940-5941.pdf),
accessed 2026-10-27. The metadata records source locations and SHA-256 digests
of the downloaded driver files and the complete indexed PDF text extraction.
The extraction digest is deliberately identified as a text digest, not a digest
of the PDF binary. Vendor downloads remain outside the repository.

The importer is an acquisition aid. It reads register, reset, field-mask,
field-position and low-level setting declarations; reconciles PDF summary and
bit-description tables by address; handles shared interrupt and sequence timer
tables; and retains source alternatives. It does not import or derive the
vendor driver's implementation. Driver expressions can establish documented
field encodings and mapping evidence without supplying generated C code.
Only canonical metadata feeds rendering; rendering needs no network or vendor
checkout. Regeneration of acquisition metadata requires the permitted sources.

## Evidence decisions

A repeated summary and detail in one data sheet are one publication, not two
independent votes. Register declarations, prose about a fixed identifier, field
details, and runtime identifier checks have different evidential roles. A
majority is never manufactured by counting repeated lines, reviewers, aliases,
or table occurrences. Genuine unresolved numeric attributes are `null` and
have no generated numeric macro. The generated comment explains the omission
and preserves candidates, source locations, and the reason.

`ADIID` at address `0x0400` is `0x4144`, including its `ADIID[15:0]` field.
The driver's reset declaration is zero, but the same header explicitly defines
`AD5940_ADIID` as fixed `0x4144` (line 3512), and the reset path checks that value
in `ad5940.c` (lines 2936–2939). Data sheet page 28 also identifies the fixed
value in its prose, summary, register heading, and field detail. Those repeated
PDF occurrences are supporting context, not independent votes. The old
block-qualified `AFECON_ADIID` source name maps to canonical register `ADIID`;
`AFECON` is the vendor header's grouping label.

The complete conflict ledger is embedded in `registers.json`. It includes:

- Register reset disagreements for CHIPID, CALDATLOCK, PSWSTA, NSWSTA,
  INTCSEL1, AFEGENINTSTA, CLKEN1, HPOSCCON/HSOSCCON, and LOSCTST.
- CHIPID's data sheet full reset `0x5502`, revision-field reset `3`, and driver
  reset `0`; the unresolved register and revision reset macros are omitted.
- ADCFILTERCON.ADCCLK's field reset versus the full-register reset.
- DATAFIFORD and SWRSTCON field-width disagreements. Disputed position,
  width, and mask constants are omitted together.
- Named driver fields overlapping regions marked reserved in the data sheet.
  These retain source-specific identities and conflict notes; reserved and
  writable masks are not invented from a preferred source.

A register's read-only access establishes writable mask zero. Otherwise a
writable mask is available only when every named field's access is resolved.
An unlisted driver bit is not assumed reserved. Reserved regions come from
explicit PDF table rows; driver/PDF reservation disagreements make the
aggregate reserved mask unknown. Reserved rows and the driver's misspelled
`RESRVED` row generate no individual field macros. Required reserved bit
patterns remain documented in register comments.

## Coverage and representation

Functional output blocks follow data sheet sections. The vendor header's
original groups are retained as `driver_block` provenance. Driver-only
registers are placed according to their documented function and marked as
inferred grouping. Aliases are reconciled by address or identical field range,
with the original driver spelling retained. A broad driver aggregate such as
LPTIASW0.TIASWCON is recorded in `legacy_aliases` when individual PDF switch
fields replace it; duplicate aggregate macros are not emitted.

The supplementary [driver setting inventory](../data/driver_settings.json)
classifies all 428 active high-level object-like definitions in the selected
header section. Direct encodings are mapped through explicit source evidence;
composite settings, software selectors, unsupported assignments, and protocol
constants retain their meanings and reasons without being disguised as one
field encoding. Canonical metadata embeds this inventory so release rendering
remains self-contained. Generated comments retain differing PDF and driver
meanings as source-qualified alternatives, including the SYSBW zero-setting
conflict.

All imported register addresses and literal reset definitions, field positions
and masks, low-level enums, aliases, unresolved attributes, and detailed PDF
settings remain traceable in the metadata. Numerical settings are unshifted.
Field width and mask are derived from contiguous bit ranges, then checked for
consistency. Register storage width follows the documented driver transaction
width boundary: addresses `0x1000` through `0x3014` use 32 bits; the remaining
listed registers use 16 bits. Mask complements, where supported by explicit
reserved coverage, are limited to that width.

PDF extraction joins line continuations and removes page furniture. Collapsed
power notation in formulas is rendered explicitly (`2^30`, `2^20`, `2^18`,
`2^17`) rather than as misleading integers such as 230. The driver explicitly
corroborates the waveform frequency denominator `2^30` for second-generation
silicon (header lines 3526–3532; implementation lines 1262–1269). The header
also records earlier silicon's 20-bit word and `2^26` denominator. Conflicting
calibration resolutions and numerical examples are preserved as source
alternatives rather than silently reconciled. Narrative conditions and
sequence rules belong to the functional block notes and the field comments.

## Updating evidence

All scripts live in `scripts/`. To reacquire metadata from temporary references:

```sh
python scripts/import_registers.py \
  --driver /path/outside/repository/ad5940.h \
  --pdf-text /path/outside/repository/full-indexed-pdf-text.txt
```

Keep the matching `ad5940.c` beside the header. Inspect the conflict ledger,
coverage counts, source hashes, aliases, and extraction quality before accepting
new metadata. Run the generator and independent verification checks documented
in [verification.md](verification.md). Source updates can change facts and must
be reviewed; a parser run alone is not a factual accuracy proof.
