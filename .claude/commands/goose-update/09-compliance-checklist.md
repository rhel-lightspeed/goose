# Phase 9: Bugzilla Compliance Checklist (BZ#2428704)

Before declaring the update ready, verify ALL of these. Present to user as
PASS/FAIL.

Requires: All previous phases completed.

---

## Package Identity
- [ ] Package name is `goose` (not `rust-goose`)
- [ ] `Conflicts: golang-github-pressly-goose` is present
- [ ] `ExcludeArch: %{ix86}` is present

## Build System
- [ ] `BuildRequires: cargo-rpm-macros >= 25` (minimum for vendored builds)
- [ ] `%constrain_build` macro is present (prevents OOM on builders)
- [ ] `%cargo_prep -v vendor` used in `%prep`
- [ ] `%cargo_build` used in `%build`
- [ ] `%cargo_vendor_manifest` called in `%build`
- [ ] `%{cargo_license_summary}` called in `%build`
- [ ] `%{cargo_license} > LICENSE.dependencies` called in `%build`
- [ ] `%cargo_test` used in `%check`
- [ ] `%cargo_generate_buildrequires` NOT used (forbidden with vendored builds)

## System Libraries
(Only check crates still present after Phase 5.2.1 — skip any that were dropped)
- [ ] `bzip2-sys` pruned, `pkgconfig(bzip2)` in BuildRequires
- [ ] `libdbus-sys` pruned, `dbus-devel` in BuildRequires
- [ ] `libsqlite3-sys` pruned, `pkgconfig(sqlite3)` in BuildRequires
- [ ] `onig_sys` pruned, `oniguruma-devel` in BuildRequires
- [ ] `ring` pregenerated objects stripped via `prune_vendor`
- [ ] `zstd-sys` pruned, `libzstd-devel` in BuildRequires
- [ ] `RUSTONIG_SYSTEM_LIBONIG=1` set in BOTH `%build` and `%check`
- [ ] Any new `-sys` crates from Phase 5.2.2 have `prune_vendor` + BuildRequires

## Forbidden Content
- [ ] No `aws-lc` / `aws-lc-rs` crates in vendor tarball
- [ ] No `rustls` crate in vendor tarball (all TLS via native-tls/OpenSSL)
- [ ] No prebuilt `.o` / `.a` / `.so` / `.dll` files in vendor tarball
  (outside of directories handled by `prune_vendor`)
- [ ] No executable `.rs` files (chmod fix in `%prep`)

## Licensing
- [ ] License tag is valid SPDX expression
- [ ] All bundled JS/CSS have license files (Source2-Source7 or upstream)
- [ ] `cargo-vendor.txt` listed as `%license` in `%files`
- [ ] `LICENSE.dependencies` listed as `%license` in `%files`
- [ ] All `Provides: bundled()` entries present and versioned

## Content Cleanup
- [ ] `generate-vendor-tarball.sh` included as Source99
- [ ] `%prep` removes `documentation/` (keeps logo images)
- [ ] `%prep` removes `ui/` (Electron app)
- [ ] `%prep` removes `bin/` (hermit tools)
- [ ] `%prep` removes `services/` (Discord bot)
- [ ] `%prep` removes `test_image.jpg` (unclear copyright)

## Platform Conditionals
- [ ] RHEL-conditional patches properly gated (`%if 0%{?rhel}`)
- [ ] EPEL 9 sqlite requirement present
  (`Requires: sqlite-libs >= 3.34.1-10`)
