# Phase 8: Spec File Updates

Update all remaining spec file sections that may be affected by the version
change.

Requires: Phases 5-7 completed (compliance, bundled content, and licenses
handled).

---

## 8.1 Binary Targets

Check if new binary targets were added upstream:

```bash
grep -r '^\[\[bin\]\]' goose-{TARGET_VERSION}/Cargo.toml goose-{TARGET_VERSION}/crates/*/Cargo.toml
```

Current binaries: `goose`, `goosed`. If new ones appeared, add them to
`%install` and `%files`.

### 8.1.1 Man Pages

The `goose-cli` crate includes a `generate_manpages` binary that generates ROFF
man pages from the clap CLI definitions. Verify that:

1. The `generate_manpages` binary target still exists in
   `crates/goose-cli/Cargo.toml`
2. The `%build` section runs `target/rpm/generate_manpages` after `%cargo_build`
3. The `%install` section installs `target/man/*.1` to `%{_mandir}/man1/`
4. The `%files` section includes `%{_mandir}/man1/goose*.1*`

If upstream changed the man page generator location or output format, update
accordingly.

## 8.2 BuildRequires

Verify all BuildRequires are still correct. Phase 5.2 handles adding/removing
BuildRequires for `-sys` crates specifically — this step is for everything else.

Check that:
- Each BuildRequires has an inline comment explaining which vendored crate or
  feature needs it
- `pkgconfig()` dependencies are used where available (per Fedora guidelines)
- System library packages use `-devel` variants
- `cargo-rpm-macros >= 25` is present (required for vendored builds)
- No BuildRequires remain for `-sys` crates that were dropped in Phase 5.2.1

## 8.3 Test Skips

Review the `%check` section. Skipped tests may need updating if:
- Test function names changed upstream
- Tests were removed upstream (remove skip)
- New tests need skipping (network/DNS tests, tests requiring specific
  resources, tests with potential copyrightable content)

Each test skip must have a comment explaining the category of skip reason.

## 8.4 %prep Section

Verify these cleanup operations still reference valid paths:
- `documentation/` folder removal (keep only `static/img/logo_{dark,light}.png`)
- `ui/` folder removal (Electron desktop app)
- `bin/` folder removal (hermit bootstrap tools)
- `services/` folder removal (Discord bot)
- `test_image.jpg` removal (unclear copyright)

If upstream reorganized their directory structure, update these paths.

## 8.5 Vendored Crate Workarounds in %prep

Check if these workarounds in `%prep` are still needed:

1. **posthog-rs reqwest version pin**: Check if
   https://github.com/PostHog/posthog-rs/pull/55 was merged. If the new goose
   version uses the updated posthog-rs, remove the sed workaround.

2. **zstd pkg-config feature injection**: Check if upstream zstd-sys crate now
   includes `pkg-config` in default features. If so, remove the sed workaround.
   Also verify that no dependency in the chain disables defaults — see Phase
   5.2.3 for the full check.

3. **Cargo checksum clearing**: Any `prune_vendor` or sed workaround that
   modifies vendored crate files must also patch `.cargo-checksum.json`.

## 8.6 Build-Time Feature Flags

Downstream feature selection is expressed as explicit cargo arguments rather
than patched Cargo.toml defaults. Verify all three call sites use identical
flags after every version update.

**The canonical feature set** (stored in `%{downstream_features}`):
```
native-tls,otel,telemetry,system-keyring,disable-update
```

`%cargo_build` and `%cargo_test` use the cargo-rpm-macros short options:
`-n` = `--no-default-features`, `-f <list>` = `--features <list>`.

### 8.6.1 Spec `%build` section

`%cargo_build` must carry both flags:

```
%cargo_build -n -f "%{downstream_features}"
```

### 8.6.2 Spec `%check` section

`%cargo_test` must carry the same flags (before the `-- --` separator):

```
%cargo_test -n -f "%{downstream_features}" -- -- ${skip-}
```

### 8.6.3 `generate-vendor-tarball.sh`

`cargo vendor-filterer` must carry the same flags so the vendor tarball is
generated with only the crates needed for the downstream feature set. Without
`--no-default-features`, upstream defaults (rustls-tls, aws-providers, …) would
pull in forbidden content (rustls crates, aws-lc-rs):

```bash
cargo vendor-filterer "${PLATFORM_ARGS[@]}" \
    --no-default-features \
    --features native-tls,otel,telemetry,system-keyring,disable-update \
    --versioned-dirs
```

### 8.6.4 When to change the feature set

Only change these flags when a new upstream feature replaces or augments one of
the five listed. When that happens, update **all three call sites** atomically
and re-generate the vendor tarball. Never add features that pull in forbidden
content (see Phase 5 and the compliance checklist).

## 8.7 Source and Patch Declarations

When adding new `Source` or `Patch` tags to the spec, verify these rules:

1. **All `Source` and `Patch` tags MUST be declared unconditionally** — never
   wrap them in `%if`/`%endif` blocks. The SRPM must always contain all files
   regardless of the target distribution.

2. **Use `%autopatch` ranges in `%prep` for conditional application.** The
   current scheme uses patch number ranges to control when patches are applied:
   - `%autopatch -p1 -M 799` — applies all patches up to 799 (universal)
   - `%autopatch -p1 -m 800 -M 899` — RHEL-only patches, gated behind
     `%if 0%{?rhel}`

3. **Assign new patches to the correct number range:**
   - `0000-0099` — Dependency patches (Cargo.toml modifications)
   - `0100-0199` — Vendor-targeting patches (paths start with `vendor/`,
     applied from source root via `%autopatch -p1 -M 799`)
   - `0200-0799` — General upstream/downstream patches
   - `0800-0899` — RHEL-only patches (applied conditionally in `%prep`)

4. **Each `Patch` tag must include a comment** explaining what the patch does
   and why it exists.

5. **Each `Source` tag must include a comment** if its purpose is not obvious
   from the filename.

If any existing `Source` or `Patch` tags are wrapped in conditionals, refactor
them: move the tag outside the conditional and use `%autopatch` ranges or
selective `%patch` calls in `%prep` instead.
