# Goose Version Update Process

This document explains how to update the goose RPM package to a new upstream
version using the Claude Code commands in this repository.

## Prerequisites

- **Claude Code** installed and configured
- **Toolbox container `tdx`** with: `cargo`, `fedpkg`, `rpmspec`, `spectool`,
  `cargo-license`, `rg` (ripgrep)
- Access to the goose packaging repository
- Familiarity with RPM spec files and Fedora packaging basics

## Quick Start

To run the full update process:

```
/goose-update/00-full-update 1.35.0
```

This orchestrates all 10 phases sequentially, pausing for user confirmation at
key decision points.

To re-run a specific phase (e.g., just the license audit):

```
/goose-update/07-license-audit
```

## Update Phases

The update process is split into 10 phases, each handling a distinct concern.
The orchestrator (`00-full-update`) reads each phase file on demand and follows
its instructions.

```
Phase 1: Pre-flight ──> Phase 2: Source ──> Phase 3: Patch Rebase ──┐
                                                                     │
              ┌──────────────────────────────────────────────────────┘
              │
              v
         Phase 4: Vendor Tarball
              │
              ├──> return to Phase 3.6 (test vendor patches)
              │
              v
         Phase 5: Dependency Compliance
              │
              v
         Phase 6: Bundled Content Audit
              │
              v
         Phase 7: License Audit
              │
              v
         Phase 8: Spec File Updates
              │
              v
         Phase 9: Compliance Checklist
              │
              v
         Phase 10: Build Verification ──> Done
```

### Phase 1: Pre-flight Checks

Validates that the target version is safe to package:
- Checks for **blocking dependencies** (v8, deno-core, swc, wasm-bindgen) in
  the upstream `Cargo.lock`
- Analyzes **feature flags** to determine which to enable/disable
- Reviews the **upstream changelog** for breaking changes, new binaries, and
  dependency changes

If blockers are found, the update stops here with an explanation.

### Phase 2: Source Update

Simple mechanical steps:
- Updates the `Version:` tag in `goose.spec`
- Downloads the new source tarball with `spectool -g`

### Phase 3: Patch Rebase

The most critical phase. Tests all existing patches against the new source:
- **0000-0099**: Dependency patches (Cargo.toml modifications)
- **0100-0199**: Vendor-targeting patches (paths start with `vendor/`)
- **0800-0899**: RHEL-only patches (applied conditionally)

Patches are classified as: applies cleanly, needs rebase, merged upstream
(drop), or no longer relevant. Dependency patches (0000, 0001) almost always
need regenerating when upstream changes dependencies.

**Note:** Step 3.6 (vendor patches) is deferred until after Phase 4.

### Phase 4: Vendor Tarball Generation

Updates `generate-vendor-tarball.sh` with any patch changes, then runs it to
produce the new vendor tarball. After this, Phase 3.6 runs to test
vendor-targeting patches.

### Phase 5: Dependency Compliance Audit

Enforces Fedora package review (BZ#2428704) rules:
- Verifies **forbidden crates** (rustls, aws-lc) are not in the dependency tree
- Checks which **-sys crates** are still needed and drops stale ones
- Detects **new -sys crates** that need `prune_vendor` + `BuildRequires`
- Scans for **prebuilt binaries** (`.o`, `.a`, `.so`) in the vendor tarball

### Phase 6: Bundled Content Audit

Identifies non-crate artifacts that need `Provides: bundled()` entries:
- **Sublime syntax definitions** from the `syntect` crate
- **Syntect themes** bundled in assets
- **Minified JS/CSS** libraries (Chart.js, D3, Leaflet, Mermaid, etc.)
- **Other embedded data** via `include_bytes!()` / `include_str!()`

Produces a summary table of what to add, remove, or update in the spec.

### Phase 7: License Audit

Validates all licenses against Fedora requirements:
- Runs `cargo license` for an early preemptive check
- Cross-references against the Fedora **approved** and **not-allowed** license
  lists
- Updates the `License:` SPDX expression if needed
- Checks bundled JS/CSS license files

### Phase 8: Spec File Updates

Catches everything else in the spec:
- New **binary targets** and **man pages**
- **BuildRequires** correctness
- **Test skips** in `%check`
- **%prep cleanup** paths (documentation, ui, bin, services)
- **Vendored crate workarounds** (checks if upstream fixed them)
- **Source/Patch declarations** (unconditional, correct number ranges)

### Phase 9: Compliance Checklist

Final pass/fail verification against the full BZ#2428704 requirements:
package identity, build system, system libraries, forbidden content, licensing,
content cleanup, and platform conditionals.

### Phase 10: Build Verification

- Builds the SRPM locally with `fedpkg srpm`
- Notes that `%autochangelog` handles the changelog automatically
- Suggests next steps: review diff, create PR, push for Packit/COPR builds

## After the Update

Once the version update is complete, the commands will self-update:
- Patch names and numbers in Phase 3
- -sys crate table in Phase 5
- Bundled content lists in Phase 6
- Workarounds in Phase 8 (drop resolved, add new)
- Compliance checklist in Phase 9

This keeps the instructions accurate for the next update cycle. See
`AGENTS.md` for full details on the self-improvement process.

## Troubleshooting

### Patch fails to apply

Check if the change was merged upstream (`git log` on the upstream repo for
the relevant files). If merged, drop the patch. If not, rebase manually
against the new source.

### Forbidden dependency detected

Run `cargo tree -I <crate>` to see the full dependency chain. Usually this
means a feature flag needs to be disabled in the 0001 patch, or a new entry
needs to be added to the blocked dependencies list.

### New -sys crate found

Check `build.rs` to see if it uses `pkg_config` or `cc::Build`. If it bundles
C source that has a Fedora system package, add a `prune_vendor` call and
`BuildRequires`. If no system package exists, evaluate whether it contains
prebuilt objects.

### License not on approved list

Check the Fedora [approved licenses](https://docs.fedoraproject.org/en-US/legal/license-approval/)
and [not-allowed licenses](https://docs.fedoraproject.org/en-US/legal/not-allowed-licenses/)
lists. If the license needs legal review, file a request on the Fedora legal
mailing list before proceeding.

### SRPM build fails

Common causes:
- Missing Source/Patch file referenced in spec
- Syntax error in spec (usually from manual edits)
- `%prep` path references to directories that no longer exist in the new version
