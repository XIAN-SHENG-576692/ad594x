# Verification plan

## Current CI

[Workflow](../.github/workflows/ci.yml): pushes, pull requests, manual dispatch.
Runs [bootstrap/check commands](development.md#bootstrap-and-current-checks).
[Scaffold check](../scripts/check-scaffold.sh) enforces required docs, ignored
output, bootstrap syntax, Jinja2 availability, and empty template directories.

## Acceptance gates

1. Generation: deterministic output; valid default, custom, and empty prefixes;
   uppercase/lowercase mapping; invalid-name and collision rejection; all
   supported type suffixes; include guards and repeated inclusion; consistent
   filenames/includes/contracts; every project-authored C/header/ACSL artifact
   traceable to a Jinja template.
2. Build: compile generated library, examples, and tests with strict warnings;
   verify each supported compiler/target configuration and all prefix cases.
3. Runtime: Unity assertions plus FFF transport fakes verify transactions,
   returned state, status propagation, and unchanged outputs on errors. Cover
   arithmetic boundaries, wire encoding, invalid input, and transport failures.
   Keep production core tests independent of device hardware.
4. Analysis: cppcheck examines generated C with target defines and include
   paths; actionable diagnostics fail CI. Record justified suppressions.
5. Formal: Frama-C/WP receives correctly attached external ACSL contracts and
   actual target machine settings. Establish attachment with a deliberately
   false-contract negative control. Fail on unproved/unknown/timed-out goals,
   missing expected obligations, or analysis errors; publish proof reports and
   explicit trusted transport assumptions. Process exit success alone does not
   establish proof success. Inspect integer/float coverage before making claims.

As gates become executable, add dedicated CI jobs and matching
`init-<PURPOSE>-<HOST>.sh` bootstraps. Upload diagnostics/rendered artifacts on
failure; never silently skip missing tools or generated inputs. Runtime tests,
cppcheck, and proofs remain distinct evidence.
