# AGENTS.md

## Project Overview

This is a Fedora/RHEL RPM packaging repository for
[goose](https://github.com/block/goose), an AI agent framework written in Rust.
The package uses vendored dependencies, downstream patches, and must comply with
Fedora packaging guidelines and a Fedora package review (BZ#2428704).

## Repository Structure

```
goose.spec                 # RPM spec file
generate-vendor-tarball.sh # Script to produce the vendored crate tarball
0000-*.patch               # Dependency patches (Cargo.toml modifications)
0001-*.patch               # ...
0100-*.patch               # Vendor-targeting patches (applied from source root)
0800-*.patch               # RHEL-only patches (applied conditionally)
*.license                  # License files for bundled JS/CSS libraries
.claude/commands/          # Claude Code slash commands
docs/                      # Human-readable documentation
```

## Claude Code Commands

All update-related commands live under `.claude/commands/goose-update/`:

| Command | Purpose |
|---------|---------|
| `/goose-update/00-full-update` | Run the full 10-phase version update |
| `/goose-update/01-preflight` | Version blockers, feature flags, changelog |
| `/goose-update/02-source-update` | Update spec version, download tarball |
| `/goose-update/03-patch-rebase` | Test and rebase all patches |
| `/goose-update/04-vendor-tarball` | Update vendor script, generate tarball |
| `/goose-update/05-dependency-compliance` | Forbidden crates, -sys crates, prebuilt scan |
| `/goose-update/06-bundled-content` | Sublime syntax, themes, JS/CSS, embedded assets |
| `/goose-update/07-license-audit` | License validation, SPDX compliance |
| `/goose-update/08-spec-updates` | Binaries, BuildRequires, test skips, %prep |
| `/goose-update/09-compliance-checklist` | Full BZ#2428704 pass/fail checklist |
| `/goose-update/10-build-verification` | SRPM build, changelog, next steps |

The orchestrator (`00-full-update`) contains shared compliance context and reads
each phase file sequentially. Individual phases can be invoked standalone to
re-run a specific step.

## Key Constraints

- **No pushing**: Never push to any remote. Branches and commits are fine.
- **Fedora compliance**: All changes must follow Fedora Packaging Guidelines,
  Fedora Rust Packaging Guidelines, and the approved/not-allowed license lists.
- **Patch declarations**: `Source` and `Patch` tags are always unconditional.
  Conditionals are applied in `%prep` using `%autopatch` ranges.

## Self-Improvement After Version Updates

After completing a version update (all 10 phases), review what changed during
the process and update the command files and this AGENTS.md to stay current.
This keeps the instructions accurate for the next update cycle.

### What to update

**Always check these after each update:**

1. **Patch Series Structure** (`03-patch-rebase.md`):
   - Update patch names and numbers if patches were added, dropped, or renamed
   - Update the descriptions to match current patch purposes
   - Update the `PATCHES` array reference for `generate-vendor-tarball.sh`

2. **System Library Table** (`05-dependency-compliance.md`):
   - Add new `-sys` crates that were discovered and handled
   - Remove `-sys` crates that are no longer vendored
   - Update the `prune_vendor` patterns if crate versions changed

3. **Bundled Content** (`06-bundled-content.md`):
   - Note any new JS/CSS libraries or embedded assets discovered
   - Update crate names if autovisualizer assets moved to a different crate

4. **Workarounds** (`08-spec-updates.md`):
   - Remove workarounds for issues that were fixed upstream (e.g., posthog-rs,
     zstd pkg-config)
   - Add new workarounds that were needed for this version
   - Update upstream PR/issue links

5. **Compliance Checklist** (`09-compliance-checklist.md`):
   - Add checklist items for any new `-sys` crates from step 2
   - Remove items for dropped crates
   - Add items for any new compliance requirements discovered

6. **This file** (`AGENTS.md`):
   - Update the Repository Structure section if files were added/removed
   - Update the patch numbering if the scheme changed

7. **CodeRabbit config** (`.coderabbit.yaml`):
   - If new file types or paths were added to the repo, add corresponding
     `path_instructions` entries so CodeRabbit reviews them correctly
   - Update existing path instructions if review criteria changed

### How to update

After the user confirms the version update is complete:

1. Review all spec file changes (`git diff`) to identify what changed
2. Compare the current command files against the actual state
3. Edit the relevant `.claude/commands/goose-update/*.md` files
4. Update this `AGENTS.md` if the repo structure changed
5. Show the user what was updated and ask them to confirm
