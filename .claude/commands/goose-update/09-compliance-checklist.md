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

## Feature Flags
All three call sites must carry identical flags. Upstream defaults include
`rustls-tls` and `aws-providers`, which pull in forbidden content; they must
be suppressed by `-n` (`--no-default-features`). The cargo-rpm-macros short
options are `-n` (no-default-features) and `-f <list>` (features) — there is
no `-p`/`--package` short option; a bare `-p` errors with `Unknown option p
in cargo_build(naf:)`. A literal `--` after the macro's own flags passes
everything following it through raw to the underlying `cargo` invocation,
where `--package <pkg>` is a real cargo flag.
`%cargo_build`/`%cargo_test` share these flags via `%{goose_cargo_flags}`
(defined once near `%{downstream_features}`) instead of duplicating them at
each call site.
- [ ] `%global goose_cargo_flags` is defined as `-n -f "%{downstream_features}" -- --package goose-cli --ignore-rust-version`
- [ ] `%cargo_build` carries `%{goose_cargo_flags}`
- [ ] `%cargo_test` carries `%{goose_cargo_flags}` (before the second `-- ${skip-}` separator)
- [ ] `cargo vendor-filterer` in `generate-vendor-tarball.sh` carries the same `-n -f` flags
- [ ] No patch hardcoding feature selection into Cargo.toml default features
  (e.g. a "Set-downstream-feature-flags" style patch) — feature selection
  belongs in the build invocation, not a patch
- [ ] No `default-members` patched into the workspace `Cargo.toml` — package
  scoping belongs in `-- --package goose-cli` on the build invocation, not a
  patch (resolver = "2" activates `--features` names across every workspace
  member when no package is selected, which can leak forbidden deps like
  `aws-lc-rs` from crates goose-cli doesn't even depend on)
- [ ] Any comment mentioning a real macro name (e.g. `%cargo_build`) in prose
  escapes it as `%%cargo_build` — RPM expands `%word` even inside `#`
  comments, and an unescaped mention silently corrupts the generated script

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
