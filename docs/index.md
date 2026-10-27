# Documentation routes

Current scope: register metadata, Jinja2 generation, independent block headers,
concrete and prefix-only release packages. No device access implementation.

Read only relevant sections and linked constraints; do not load every doc.

- Implementation: [scope/stages](roadmap.md) and relevant architecture below.
- Generator: [architecture](architecture.md); focused C changes:
  [naming/types](architecture.md#naming-and-specialization),
  [core/transport](architecture.md#core-and-transport).
- Register sources, conflicts, and coverage: [evidence](register-evidence.md).
- Future ACSL/proofs: [contracts](architecture.md#contracts),
  [acceptance gates](verification.md#future-library-gates).
- Setup/dependencies/commands: [development](development.md).
- Tests/analysis/CI: [verification](verification.md).
- Docs-only: affected owner and maintenance below.

## Maintenance

- Keep each rule/decision in one owner; link rather than repeat.
- Update owners with behavior changes, rationale, validation, and limits;
  distinguish working commands/evidence from plans.
- Use Git for history. Link lengthy records separately; add routes for new topics.
