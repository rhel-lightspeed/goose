# Lessons Learned

A running log of surprises, mistakes, and workflow gaps discovered while
running the `goose-update` agent commands, and what was changed to prevent
them from recurring.

This file exists so the update process gets more deterministic over time
instead of relying on the agent (or the human reviewing it) to remember past
mistakes. It is not a changelog of package versions — see the `changelog`
file for that.

## How to use this file

**Before starting an update**, read this file so past gotchas are fresh
context, especially any entries tagged with a phase you're about to run.

**After finishing an update** (end of Phase 8, or whenever something
surprising happened), add a new entry at the top using the template below.
Only add an entry when something was learned that isn't already covered by
the phase files or AGENTS.md — if the existing docs already say the right
thing and the agent just failed to follow them, prefer fixing the wording in
place instead of only logging it here.

### Entry template

```
## YYYY-MM-DD — Short title

- **Version**: the goose version being packaged when this was found
- **Phase**: which phase file(s) this relates to
- **What happened**: brief description of the surprise or mistake
- **Root cause**: why it happened
- **Fix**: what was changed (files touched, e.g. a phase `.md`, AGENTS.md,
  or the spec/patches themselves) — link to the commit/PR if available
```

---

## 2026-08-14 — `%define` vs `%global` typo made the forbidden-crate check a silent no-op

- **Version**: N/A (workflow-only change, no package version bump)
- **Phase**: `03-dependency-compliance.md` (3.1 Forbidden Crates Check),
  `06-spec-updates.md` (6.6 Build-Time Feature Flags)
- **What happened**: Both phases extracted `%{downstream_features}` from the
  spec with `rg '%define downstream_features' goose.spec`, but `goose.spec`
  actually declares it with `%global`. The `rg` call matched nothing, so
  `FEATURES` was silently empty and `cargo tree --no-default-features
  --features "" -i <crate>` ran with no features enabled — not the real
  build configuration — making the "authoritative" forbidden-crate check
  meaningless without any visible error.
- **Root cause**: Copy/paste or manual typo; nothing in the phase file
  verified that its own extraction command actually returned a non-empty
  value before using it.
- **Fix**: Corrected both `rg` invocations to `%global`. General takeaway:
  any command that captures a value into a shell variable for later use
  should be treated as a "silent failure" risk — prefer checks that fail
  loudly (e.g. `[ -z "$FEATURES" ] && { echo "FAIL: could not read
  downstream_features"; exit 1; }`) instead of assuming extraction worked.

## 2026-08-14 — Feature-flag decision test made explicit in AGENTS.md

- **Version**: N/A (workflow-only change, no package version bump)
- **Phase**: `01-source-and-preflight.md` (1.5 Feature Flags Analysis),
  `03-dependency-compliance.md` (3.1 Forbidden Crates Check)
- **What happened**: The agent proposed regenerating a Cargo.toml dependency
  patch to remove a feature from a crate's `default = [...]` list, even
  though that feature was already excluded from the build because it's not
  listed in `%{downstream_features}` and every build call site passes
  `--no-default-features`.
- **Root cause**: Phase 1.5 previously said features "should be evaluated
  case-by-case" and "MUST be disabled" without specifying *how* — the agent
  filled the gap by editing `Cargo.toml` directly, duplicating what
  `--no-default-features` already does. AGENTS.md stated the "never patch
  Cargo.toml defaults" rule but didn't give a concrete, runnable test to
  decide when a dependency patch is actually justified (the
  `0004-aws-lc-rs-feature-flag.patch` case, where a crate pulls in a forbidden
  dependency *unconditionally*, regardless of our top-level feature flags).
- **Fix**: Added a "Do not patch Cargo.toml just to 'turn off' a feature"
  section to AGENTS.md with an explicit `cargo tree --no-default-features
  --features "%{downstream_features}" -i <crate>` decision test. Rewrote
  Phase 1.5 to run that test and stop turning ambiguous "case-by-case"
  judgment calls into a concrete decision tree. Tightened Phase 3.1's
  guidance to point at the same test when a forbidden crate is found. Also
  tightened a few other phases to STOP and ask the user instead of silently
  guessing (Phase 2.2 dropping "no longer relevant" patches, Phase 3.2.2
  new `-sys` crates with no system package).
