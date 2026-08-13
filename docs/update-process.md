# Goose Version Update Process

This document explains how to update the goose RPM package to a new upstream
version using the agent commands in this repository.

## Prerequisites

- **Agent** with access to shell tools (Claude Code, Goose, etc.)
- **Toolbox container `tdx`** with: `cargo`, `fedpkg`, `rpmspec`, `spectool`,
  `cargo-license`, `rg` (ripgrep), `fd`, `gh` (GitHub CLI)
- Access to the goose packaging repository
- Familiarity with RPM spec files and Fedora packaging basics

## Quick Start

To run the full update process:

```
/goose-update/00-full-update 1.35.0
```

This orchestrates all 8 phases sequentially, pausing for user confirmation at
key decision points.

To re-run a specific phase (e.g., just the license audit):

```
/goose-update/05-license-audit
```

## Design Principles

The update commands follow these principles:

1. **Discovery over declaration** — Commands don't hardcode patch names, crate
   lists, or workaround details. The agent discovers the current state by
   reading files and running tools.

2. **Local over remote** — All analysis works against the tarball downloaded
   via `spectool -g`. Individual files are never fetched from GitHub.

3. **Verify deterministically** — Each phase ends with verification checks
   using `patch --dry-run`, `fd`, `rg`, `diff`, etc.

4. **`.orig` pattern** — Before modifying any file in the extracted source,
   copy it to `.orig`. Generate patches with `diff -u --label`.

5. **Each phase owns its verification** — No deferred checking. If a phase
   can't verify its own work, it stops.

6. **Stop instead of guessing** — When a phase file's decision tree runs out
   (a patch is ambiguous, a new `-sys` crate has no system package, a new
   upstream feature isn't in `%{downstream_features}`), the agent stops and
   asks rather than silently picking an option.

7. **Learn from past runs** — `docs/lessons-learned.md` records past mistakes
   and workflow gaps. It's read at the start of every update (Phase 1) and
   appended to at the end (Phase 8) when something new surfaces.

## Update Phases

```
Phase 1: Source Setup & Pre-flight
         │
         v
Phase 2: Patches & Vendor Tarball
         │
         v
Phase 3: Dependency Compliance
         │
         v
Phase 4: Bundled Content Audit
         │
         v
Phase 5: License Audit
         │
         v
Phase 6: Spec File Updates
         │
         v
Phase 7: Final Compliance Gate
         │
         v
Phase 8: Changelog & Build Verification ──> Done
```

### Phase 1: Source Setup & Pre-flight

Reads `docs/lessons-learned.md` for context, verifies all required tools are
available (see AGENTS.md), then updates the spec version, downloads and
extracts the tarball locally, and validates that the target version is safe
to package:
- Checks for **blocking dependencies** (v8, deno-core, swc) in `Cargo.lock`
- Compares upstream **feature names** against `%{downstream_features}` — does
  not edit `Cargo.toml` (see AGENTS.md's "Downstream Feature Flags")
- Reviews the **upstream changelog** via `gh release view`

The extracted source is kept for subsequent phases.

### Phase 2: Patches & Vendor Tarball

Handles the full patch lifecycle in one pass:
- Tests all non-vendor patches with `patch -p1 --dry-run`
- Rebases failures using the `.orig` + `diff -u --label` pattern
- Verifies and updates `generate-vendor-tarball.sh`
- Generates the vendor tarball
- Tests vendor patches (0100+) against the new vendor directory

### Phase 3: Dependency Compliance

Dynamically discovers `-sys` crates in the vendor tree and cross-references
against the spec's `%prep` section:
- Verifies **forbidden crates** are absent
- Detects **new `-sys` crates** needing `prune_vendor` + `BuildRequires`
- Removes **stale entries** for dropped crates
- Scans for **prebuilt binaries**

### Phase 4: Bundled Content Audit

Scans for non-crate artifacts needing `Provides: bundled()` entries:
syntax definitions, themes, JS/CSS libraries, embedded data files.

### Phase 5: License Audit

Validates all licenses against Fedora approved/not-allowed lists. Updates
the `License:` SPDX expression if needed.

### Phase 6: Spec File Updates

Catches everything else: binary targets, BuildRequires, test skips, `%prep`
cleanup paths, vendored crate workarounds, feature flag consistency,
Source/Patch declarations.

### Phase 7: Final Compliance Gate

Lightweight cross-cutting checks (package identity, build system macros,
declaration rules) plus a summary table collecting pass/fail from all phases.

### Phase 8: Changelog & Build Verification

Filters upstream release notes (removes disabled features, UI/desktop,
excluded platforms) and writes RPM changelog entry. Then builds the SRPM
locally, runs a retro against `docs/lessons-learned.md` (appending an entry
and proposing phase-file edits if something new was learned), and suggests
next steps (review diff, create PR, push for Packit/COPR builds).

## Troubleshooting

### Patch fails to apply

Check if the change was merged upstream by examining the target files in the
new source. If merged, drop the patch. If not, rebase using the `.orig`
pattern.

### Forbidden dependency detected

Run `cargo tree --no-default-features --features "%{downstream_features}" -i
<crate>` (the same flags used at build time) to see if it's actually
reachable. If it's *not* reachable with those flags, there's nothing to do —
some other feature combination pulls it in but ours doesn't. If it *is*
reachable even with those flags, a crate is pulling it in unconditionally
(e.g. via a required dependency, or another crate's own defaults); only then
does it need a dependency patch. See "Downstream Feature Flags" in AGENTS.md
— never patch `Cargo.toml` just to remove a feature that's already absent
from `%{downstream_features}`.

### New -sys crate found

Inspect `build.rs` to see if it uses `pkg_config` or `cc::Build`. If it
bundles C source that has a Fedora system package, add `prune_vendor` +
`BuildRequires`. If no system package exists, evaluate for prebuilt objects.

### License not on approved list

Check the Fedora approved and not-allowed license lists. If legal review is
needed, file a request on the Fedora legal mailing list before proceeding.

### SRPM build fails

Common causes: missing Source/Patch file, spec syntax error, `%prep` paths
referencing directories that no longer exist in the new version.
