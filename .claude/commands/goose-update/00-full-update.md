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

## Fedora Packaging Compliance

This package MUST strictly follow:
- Fedora Packaging Guidelines (https://docs.fedoraproject.org/en-US/packaging-guidelines/)
- Fedora Rust Packaging Guidelines (https://docs.fedoraproject.org/en-US/packaging-guidelines/Rust/)

All licenses MUST be valid SPDX identifiers listed in the Fedora approved
license list:
- Approved licenses: https://docs.fedoraproject.org/en-US/legal/license-approval/
- Not allowed licenses: https://docs.fedoraproject.org/en-US/legal/not-allowed-licenses/

Key Rust packaging rules that apply to this package:
- `BuildRequires: cargo-rpm-macros >= 25` (required for vendored builds)
- `%cargo_prep -v vendor` in `%prep` (sets up vendored build)
- `%cargo_build` in `%build`
- `%cargo_vendor_manifest` MUST be called in `%build`
- `%{cargo_license_summary}` MUST be called in `%build`
- `%{cargo_license}` MUST generate `LICENSE.dependencies`
- `cargo-vendor.txt` MUST be listed as `%license` in `%files`
- `LICENSE.dependencies` MUST be listed as `%license` in `%files`
- `%cargo_generate_buildrequires` MUST NOT be used with vendored builds
- `%cargo_test` in `%check`
- License tag must be a valid SPDX expression covering all compiled code
- All bundled content must have `Provides: bundled()` entries

Source and Patch declaration rules:
- `Source` and `Patch` tags MUST always be declared unconditionally — never
  wrap them in `%if`/`%endif` conditionals
- Distribution-specific conditionals (e.g., `%if 0%{?rhel}`) MUST be applied
  in `%prep` when applying patches (using `%autopatch` with `-m`/`-M` ranges),
  not on the declaration lines
- This ensures the SRPM always contains all files regardless of build target,
  and the build system decides at `%prep` time which patches to apply

---

## Execution

Execute each phase sequentially by reading its file from
`.claude/commands/goose-update/` and following its instructions. Ask the user
for confirmation between phases when indicated.

If any phase fails, stop and report clearly what failed and why. Never silently
skip a compliance check. Always show the user what changed before proceeding.

| Phase | File | Description |
|-------|------|-------------|
| 1 | `goose-update/01-preflight.md` | Version blocker analysis, feature flags, changelog review |
| 2 | `goose-update/02-source-update.md` | Update spec version, download new tarball |
| 3 | `goose-update/03-patch-rebase.md` | Test and rebase all patches (defer 3.6 until after Phase 4) |
| 4 | `goose-update/04-vendor-tarball.md` | Update vendor script, generate tarball, then return to 3.6 |
| 5 | `goose-update/05-dependency-compliance.md` | Forbidden crates, system library linkage, prebuilt scan |
| 6 | `goose-update/06-bundled-content.md` | Sublime syntax, themes, JS/CSS, other embedded assets |
| 7 | `goose-update/07-license-audit.md` | License validation, SPDX check, License field update |
| 8 | `goose-update/08-spec-updates.md` | Binary targets, BuildRequires, test skips, %prep, Source/Patch |
| 9 | `goose-update/09-compliance-checklist.md` | Full BZ#2428704 compliance pass/fail checklist |
| 10 | `goose-update/10-build-verification.md` | SRPM build, changelog, next steps |

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
