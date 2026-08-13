# Goose Package Version Update

Update the goose RPM package to a new upstream version. This is a complex Rust
package with vendored dependencies, downstream patches, and strict compliance
requirements from the Fedora package review (BZ#2428704).

Always assume you are running inside the packaging repository root.

## Arguments

- `$ARGUMENTS`: (Optional) Target upstream version to update to (e.g. `1.24.0`).
  If not provided, check the latest release from https://github.com/aaif-goose/goose/releases
  and ask the user to confirm.

---

## Compliance Context

All project-wide rules (Fedora compliance references, forbidden dependencies,
patch numbering, feature flags, Source/Patch declaration rules) are documented
in `AGENTS.md`. Read it before starting — the phase files reference those
rules without repeating them.

Also read `docs/lessons-learned.md` before starting (Phase 1 does this too,
but read it now so you have context for the whole run, not just Phase 1).
It records past mistakes so they aren't repeated. Phase 8 ends with a retro
step that appends to it when something new is learned.

---

## Execution

Execute each phase sequentially by reading its file from
`.claude/commands/goose-update/` and following its instructions. Ask the user
for confirmation between phases when indicated.

If any phase fails, stop and report clearly what failed and why. Never silently
skip a compliance check. Always show the user what changed before proceeding.

| Phase | File | Description |
|-------|------|-------------|
| 1 | `goose-update/01-source-and-preflight.md` | Update spec version, download tarball, check blockers, features, changelog |
| 2 | `goose-update/02-patches-and-vendor.md` | Test/rebase all patches, generate vendor tarball, test vendor patches |
| 3 | `goose-update/03-dependency-compliance.md` | Forbidden crates, system library linkage, prebuilt scan |
| 4 | `goose-update/04-bundled-content.md` | Sublime syntax, themes, JS/CSS, other embedded assets |
| 5 | `goose-update/05-license-audit.md` | License validation, SPDX check, License field update |
| 6 | `goose-update/06-spec-updates.md` | Binary targets, BuildRequires, test skips, %prep, Source/Patch |
| 7 | `goose-update/07-compliance-gate.md` | Final compliance gate — cross-cutting checks + phase summary |
| 8 | `goose-update/08-changelog-and-build.md` | Write changelog, build SRPM, next steps |

Read each phase file with the Read tool as you reach it. Do not read all files
upfront — process them one at a time to keep context focused.

---

## Error Handling

- If any phase fails, stop and report clearly what failed and why
- Never silently skip a compliance check
- If a patch fails to rebase, show the exact conflict and ask the user for
  guidance
- If a new forbidden dependency is detected, explain which crate pulls it in
  (show the dependency chain if possible)
- Always show the user what changed before committing anything
- If a new license is found that may be problematic, flag it and suggest the
  user consult the Fedora legal mailing list before proceeding
