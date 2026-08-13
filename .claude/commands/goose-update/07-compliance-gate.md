# Phase 7: Final Compliance Gate (BZ#2428704)

Lightweight final verification before declaring the update ready. Each phase
already verified its own work — this phase catches cross-cutting concerns and
presents a summary.

Requires: All previous phases completed.

---

## 7.1 Package Identity

These are structural spec properties that no single phase owns. Read the spec
and verify:

```bash
rpmspec -q --qf "%{NAME}" goose.spec  # must be "goose"
rg -q 'Conflicts:.*golang-github-pressly-goose' goose.spec
rg -q 'ExcludeArch:.*ix86' goose.spec
```

- [ ] Package name is `goose` (not `rust-goose`)
- [ ] `Conflicts: golang-github-pressly-goose` is present
- [ ] `ExcludeArch: %{ix86}` is present

## 7.2 Build System Macros

Verify the spec uses the correct cargo-rpm-macros workflow for vendored builds:

```bash
rg -q 'cargo-rpm-macros >= 25' goose.spec
rg -q '%cargo_prep -v vendor' goose.spec
rg -q '%cargo_build' goose.spec
rg -q '%cargo_vendor_manifest' goose.spec
rg -q '%\{cargo_license_summary\}' goose.spec
rg -q '%\{cargo_license\}' goose.spec
rg -q '%cargo_test' goose.spec
! rg -q '%cargo_generate_buildrequires' goose.spec
```

- [ ] `BuildRequires: cargo-rpm-macros >= 25`
- [ ] `%cargo_prep -v vendor` in `%prep`
- [ ] `%cargo_build` in `%build`
- [ ] `%cargo_vendor_manifest` in `%build`
- [ ] `%{cargo_license_summary}` in `%build`
- [ ] `%{cargo_license}` generates `LICENSE.dependencies`
- [ ] `%cargo_test` in `%check`
- [ ] `%cargo_generate_buildrequires` NOT used (forbidden with vendored builds)

## 7.3 License Files in %files

```bash
rg -q 'cargo-vendor.txt' goose.spec
rg -q 'LICENSE.dependencies' goose.spec
```

- [ ] `cargo-vendor.txt` listed as `%license` in `%files`
- [ ] `LICENSE.dependencies` listed as `%license` in `%files`

## 7.4 Source/Patch Declarations

Verify no `Source` or `Patch` tags are wrapped in conditionals:

```bash
# Look for Source/Patch inside %if blocks
awk '/%if/{in_if=1} /%endif/{in_if=0} in_if && /^(Source|Patch)/' goose.spec
```

- [ ] All `Source` and `Patch` tags are unconditional

## 7.5 Summary

Collect results from this phase and all previous phase verifications. Present
to user as a pass/fail table:

| Phase | Area | Status |
|-------|------|--------|
| 1 | Source setup + pre-flight (no blockers) | |
| 2 | Patches rebase cleanly + vendor tarball | |
| 3 | Dependency compliance | |
| 4 | Bundled content declared | |
| 5 | Licenses approved + SPDX valid | |
| 6 | Spec sections updated | |
| 7 | Package identity + macros + declarations | |

If any phase reports a failure, stop and address it before proceeding to
Phase 8.
