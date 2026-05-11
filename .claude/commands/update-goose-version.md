# Goose Package Version Update

Update the goose RPM package to a new upstream version. This is a complex Rust
package with vendored dependencies, downstream patches, and strict compliance
requirements from the Fedora package review (BZ#2428704).

Always assume you are running inside the packaging repository root.

## Arguments

- `$ARGUMENTS`: (Optional) Target upstream version to update to (e.g. `1.24.0`).
  If not provided, check the latest release from https://github.com/aaif-goose/goose/releases
  and ask the user to confirm.

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

## Phase 1: Pre-flight Checks

### 1.1 Version Blocker Analysis

Before proceeding with ANY version update, check if the target version
introduces any of these **blocking dependencies**:

- `v8` or `v8-sys` — V8 JavaScript engine, extremely difficult to package
- `deno-core` or `deno_*` — Deno runtime components
- `swc` or `swc_*` — SWC compiler, complex native build
- `wasm-bindgen` — WebAssembly bindings (if pulled in as a build dep)

To check, download the upstream `Cargo.lock` for the target version and search
it locally (the file is too large for WebFetch):

```bash
curl -sL https://raw.githubusercontent.com/aaif-goose/goose/v{TARGET_VERSION}/Cargo.lock -o /tmp/goose-upstream-Cargo.lock
rg -c '^name = "(v8|v8-sys|deno-core|deno_|swc|swc_|wasm-bindgen)"' /tmp/goose-upstream-Cargo.lock
```

If any matches are found, **STOP** and warn the user:

> This version introduces blocked dependencies ({list}). Per RSPEED-2434, we
> cannot update past versions that pull in v8/deno-core/swc until upstream
> provides a way to disable those features. The current constraint is documented
> in the spec file header comment.

### 1.2 Feature Flags Analysis

Goose upstream uses Cargo feature flags. Fetch the workspace `Cargo.toml` and
check for feature definitions:

```
WebFetch https://raw.githubusercontent.com/aaif-goose/goose/v{TARGET_VERSION}/Cargo.toml
```

Also check per-crate `Cargo.toml` files for the main crates (`goose-cli`,
`goosed`, `goose-server`, etc.).

**Mandatory feature rules:**
- `native-tls` MUST always be enabled — we never use rustls
- Any feature that pulls in `v8`, `deno-core`, or `swc` MUST be disabled
- Other features should be evaluated case-by-case with the user

Report to the user:
- What features exist and what they do
- Which features are safe to enable
- Which features would pull in blocked dependencies
- Recommend which features to enable/disable

### 1.3 Upstream Changelog Review

Fetch the release notes for all versions between current and target:

```
WebFetch https://github.com/aaif-goose/goose/releases/tag/v{TARGET_VERSION}
```

Summarize for the user:
- New features added
- Dependencies added/removed/changed
- Any breaking changes
- Any new binary targets (check `[[bin]]` sections in workspace Cargo.toml)
- Any new crates added to the workspace (check for new `crates/` directories)

Ask the user to confirm they want to proceed after reviewing the summary.

---

## Phase 2: Source Update

### 2.1 Update Spec Version

Edit `goose.spec` to update the `Version:` tag to the target version.

**Do NOT** change the `Release:` tag — it uses `%autorelease`.

### 2.2 Download New Source Tarball

```bash
spectool -g goose.spec
```

---

## Phase 3: Patch Rebase

This is the most critical phase. Patches are split into two series:

### Patch Series Structure

**0000-0099 patches** — Applied to the goose source tree:
- `0000` — Remove Windows-specific dependencies (winapi/winreg) from Cargo.toml
  files across the workspace
- `0001` — Disable rustls and default features for dependencies, switch to
  native-tls in Cargo.toml
- `0002` — Patch Rust source code to use native-tls instead of rustls (separate
  from 0001 so Cargo.toml patches can be regenerated independently)
- `0003+` — CVE fixes, downstream-only fixes

**0100-0199 patches** — Target vendored crates (paths start with `vendor/`,
applied from the source root via `%autopatch -p1 -M 799`):
- `0100` — Patch ring's build.rs to never use pre-generated object files
- `0101` — Raise recursion limit for packaging

**0800-0899 patches** — RHEL-only (applied conditionally in `%prep` via
`%autopatch -p1 -m 800 -M 899` inside `%if 0%{?rhel}`):
- `0800` — Include legal disclaimer for goose proxy provider

### 3.1 Extract and Test Patches

Extract the new source and test each patch:

```bash
tar xf goose-{TARGET_VERSION}.tar.gz
cd goose-{TARGET_VERSION}
for p in ../0*.patch; do
  echo "=== Testing: $p"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

### 3.2 Classify Patch Status

For each patch, determine:

1. **Applies cleanly** — Keep as-is
2. **Applies with fuzz/offset** — Rebase (re-generate the patch)
3. **Fails** — Check if the change was merged upstream:
   - If merged upstream: **drop the patch** and remove from spec
   - If not merged but context changed: **rebase manually**
4. **No longer relevant** — If the upstream code changed so the patch target
   no longer exists, investigate and report to user

### 3.3 Regenerate Dependency Patches (0000 and 0001)

These patches modify `Cargo.toml` files across the workspace. When upstream
changes dependencies, these patches almost always need regenerating.

**Process to regenerate 0000 (Windows deps removal):**

1. In the extracted source, identify all `Cargo.toml` files that reference
   `winapi`, `winreg`, `windows-sys`, or other Windows-only crates in
   non-platform-conditional dependencies
2. Remove those dependencies (they should be behind
   `[target.'cfg(windows)'.dependencies]` but sometimes aren't)
3. Generate patch with `git diff`

**Process to regenerate 0001 (rustls → native-tls):**

1. In all `Cargo.toml` files, find dependencies using `rustls` or
   `rustls-tls` features
2. Switch them to `native-tls` feature
3. Disable default features where they pull in rustls
4. Ensure `native-tls` feature flag is always enabled for the workspace
5. Generate patch with `git diff`

**CRITICAL:** Patches 0000 and 0001 are also listed in
`generate-vendor-tarball.sh`'s `PATCHES` array because they affect
`Cargo.toml`/`Cargo.lock` which changes what gets vendored. If these patches
change, update the `PATCHES` array in that script too.

### 3.4 Check CVE Patches

For any `0xxx-Fix-for-CVE-*` patches:
- Check if the CVE was fixed in the target version's dependency tree
- If the vulnerable crate was updated upstream, the patch can likely be dropped
- If not, rebase the patch against the new version

### 3.5 Check Downstream-Only Patches

Patches like the legal disclaimer (0800) for RHEL-specific fixes should be
checked for applicability but are unlikely to conflict unless the affected files
changed significantly upstream.

### 3.6 Check Vendor Patches (0100 series)

**Note:** This step is deferred until after Phase 4 (vendor tarball generation),
since the vendor directory does not exist yet. Come back here after running
`generate-vendor-tarball.sh`.

Test vendor-targeting patches. These are applied from the source root (not
inside `vendor/`), as their paths already start with `vendor/`:

```bash
tar xf goose-{TARGET_VERSION}-vendor.tar.xz
for p in ../0100*.patch ../0101*.patch; do
  [ -f "$p" ] || continue
  echo "=== Testing: $p"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

Check if `ring` crate version changed — if so, the patch path in 0100
(`vendor/ring-{VERSION}/build.rs`) needs updating.

---

## Phase 4: Vendor Tarball Generation

### 4.1 Update generate-vendor-tarball.sh

Check the `PATCHES` array in `generate-vendor-tarball.sh`. It must list exactly
the patches that modify `Cargo.toml` or `Cargo.lock` (affecting dependency
resolution). Currently these are (verify against the actual file):

- `0000-Patch-windows-dependencies-across-workspace.patch`
- `0001-Disable-rustls-and-default-features-for-some-librari.patch`
- CVE patches that update vendored crate versions (e.g., `0003-Fix-for-CVE-*`)

If patches were added, removed, or renamed in Phase 3, update this array.

### 4.2 Generate Vendor Tarball

```bash
./generate-vendor-tarball.sh
```

---

## Phase 5: Dependency Compliance Audit

This phase enforces the rules from the Fedora package review (BZ#2428704).

### 5.1 Forbidden Crates Check

Check that these crates are NOT present in the dependency tree, or if present,
are properly handled:

| Crate | Rule |
|-------|------|
| `rustls` | Must NOT be used. All TLS must go through `native-tls` (OpenSSL) |
| `aws-lc-rs` / `aws-lc-sys` | Must be removed entirely — contains prebuilt binaries |
| `ring` | Allowed but `pregenerated/` directory MUST be stripped and patch 0100 MUST be applied |

From the extracted source directory with patches 0000-0002 applied and the
vendor tarball extracted (`tar xf goose-{TARGET_VERSION}-vendor.tar.xz`):

```bash
cargo tree -I rustls 2>/dev/null
cargo tree -I aws-lc-rs 2>/dev/null
cargo tree -I aws-lc-sys 2>/dev/null
```

If any of these produce output showing the crate in the dependency tree, the
0002 patch did not properly disable it. Go back to Phase 3 and fix.

### 5.2 System Library Linkage Verification

These vendored C library crates MUST link against system libraries, not bundle
their own. Verify the `%prep` section still prunes them correctly:

| Vendored Crate | System Package | Pruned Directory |
|----------------|----------------|------------------|
| `bzip2-sys` | `pkgconfig(bzip2)` | `bzip-*` |
| `libdbus-sys` | `dbus-devel` | `vendor` |
| `libsqlite3-sys` | `pkgconfig(sqlite3)` | `sqlite3`, `sqlcipher` |
| `onig_sys` | `oniguruma-devel` | `oniguruma` |
| `ring` | `/usr/bin/perl` | `pregenerated` |
| `zstd-sys` | `libzstd-devel` | `zstd` |

#### 5.2.1 Check if existing -sys crates are still needed

For each crate in the table above, verify it is still present in the vendor
tarball:

```bash
for crate in bzip2-sys libdbus-sys libsqlite3-sys onig_sys ring zstd-sys; do
  if ls -d vendor/${crate}-*/ >/dev/null 2>&1; then
    echo "KEEP: ${crate} still present"
  else
    echo "DROP: ${crate} no longer vendored"
  fi
done
```

For any crate marked `DROP`:
- Remove its `prune_vendor` call from `%prep`
- Remove its corresponding `BuildRequires` from the spec
- Remove the `.cargo-checksum.json` clearing for that crate if present
- If it is `onig_sys`, also remove the `RUSTONIG_SYSTEM_LIBONIG=1` environment
  variable from `%build` and `%check`

#### 5.2.2 Check for new -sys crates

Check if any NEW `-sys` crates in the vendor tarball bundle C libraries:

```bash
find vendor/ -name 'build.rs' -exec grep -l 'cc::Build\|pkg_config\|cmake::Config\|bindgen::Builder' {} +
```

Filter out crates already handled in the table above. For each new `-sys` crate
found:

1. **Identify bundled C source directories** inside the crate:

```bash
ls -d vendor/{CRATE_NAME}-*/
find vendor/{CRATE_NAME}-*/ -maxdepth 1 -type d
```

   Look for directories containing C/C++ source (`.c`, `.h`, `.cpp` files),
   prebuilt objects, or vendored library copies.

2. **Check if a Fedora system package provides this library.** Search for
   `pkgconfig()` provides or `-devel` packages:

```bash
dnf provides 'pkgconfig({LIBRARY_NAME})'
dnf search {LIBRARY_NAME}-devel
```

3. **If a system package exists:**
   - Add a `prune_vendor` call in `%prep` to strip the bundled C source
     directory, following the existing pattern:
     ```
     prune_vendor "{CRATE_NAME}-*" "{BUNDLED_DIR}"
     ```
   - Add the corresponding `BuildRequires` to the spec, using `pkgconfig()`
     where available, with an inline comment naming the vendored crate:
     ```
     BuildRequires:  pkgconfig({LIBRARY_NAME})  # {CRATE_NAME}
     ```
   - If the crate requires environment variables to use the system library
     (like `RUSTONIG_SYSTEM_LIBONIG=1` for `onig_sys`), check the crate's
     `build.rs` for env var toggles and add them to both `%build` and `%check`
   - Add the crate to the table in this section for future updates

4. **If no system package exists**, the crate may need to build its own copy —
   flag it for the user to evaluate whether it contains prebuilt objects that
   violate Fedora guidelines (see 5.3).

### 5.3 Prebuilt Object/Binary Scan

Scan for any prebuilt objects or binaries in the vendor tarball:

```bash
find vendor/ -name '*.o' -o -name '*.a' -o -name '*.so' -o -name '*.dll' -o -name '*.lib' -o -name '*.dylib' | head -50
```

If any are found outside of directories already handled by `prune_vendor`, they
must be addressed per Fedora packaging guidelines (no prebuilt binaries allowed
in source packages).

---

## Phase 6: Bundled Content Audit

This phase identifies all non-crate artifacts embedded in the source or vendor
tree that must be declared as `Provides: bundled()` in the spec file. Fedora
packaging guidelines require every bundled library or dataset shipped inside the
package to have a corresponding `Provides: bundled()` entry.

### 6.1 Scan for Bundled Sublime Syntax Definitions

The `syntect` crate bundles sublimehq/Packages syntax definitions as compiled
packdump files. These end up compiled into the binary.

1. Locate the syntect crate in the vendor tarball:

```bash
ls -d vendor/syntect-*/
```

2. Extract the list of bundled language definitions:

```bash
strings vendor/syntect-*/assets/default_newlines.packdump | grep 'Packages/' | sed 's|.*/||' | sort -u
```

3. Compare the extracted list against the existing
   `Provides: bundled(sublime-syntax-*)` entries in `goose.spec`. Report:
   - New languages added upstream (need new `Provides` lines)
   - Languages removed upstream (remove stale `Provides` lines)

4. Check the syntect crate version (from `vendor/syntect-*/Cargo.toml`) and the
   sublimehq/Packages commit hash embedded in the assets. If the packdump
   changed, update the version in
   `Provides: bundled(sublime-syntax) = {version}~git{hash}`.

### 6.2 Scan for Bundled Syntect Themes

The `syntect` crate also bundles default color themes in its `assets/` directory.

1. Check the theme list in `vendor/syntect-*/src/dumps.rs` (look for
   `add_from_folder` or theme loading code):

```bash
grep -A 20 'fn get_integrated_themeset\|ThemeSet' vendor/syntect-*/src/dumps.rs 2>/dev/null || \
grep -r 'theme' vendor/syntect-*/assets/ 2>/dev/null
```

2. Compare against existing `Provides: bundled(syntect-theme-*)` and
   `Provides: bundled(sublime-theme-*)` entries in the spec. Report any changes.

### 6.3 Scan for Bundled JavaScript and CSS Libraries

Scan the entire source tree for minified third-party JavaScript and CSS files.
Currently the `goose-mcp` crate bundles libraries for the autovisualizer, but
new crates may also embed JS/CSS assets.

1. Find all `.js` and `.css` files across all crates (excluding test folders):

```bash
find goose-{TARGET_VERSION}/crates/ \( -name '*.min.js' -o -name '*.min.css' -o -name '*.js' -o -name '*.css' \) \
  -not -path '*/target/*' -not -path '*/test*/*' | sort
```

2. For each minified file found, try to identify the library name and version
   by inspecting the file header or first few lines:

```bash
find goose-{TARGET_VERSION}/crates/ \( -name '*.min.js' -o -name '*.min.css' \) \
  -not -path '*/target/*' -not -path '*/test*/*' \
  -exec sh -c 'echo "=== {} ==="; head -5 "{}"; echo' \;
```

3. Compare each file against the existing `Provides: bundled()` entries in the
   spec. Report:
   - New JS/CSS files added (need new `Provides` lines with versions)
   - Files removed (remove stale `Provides` lines)
   - Version changes (update version in existing `Provides` lines)
   - Files where version could not be determined (flag for manual review)
   - Files found in crates other than `goose-mcp` (flag as new bundled content
     that needs its own group of `Provides` entries in the spec)

4. Non-minified JS/CSS files (e.g., `mcp-app-bridge.js`, `mcp-app-base.css`)
   that appear to be project-internal code do not need `Provides: bundled()`
   entries — only third-party libraries do. Flag any new non-minified files for
   the user to classify as internal vs. third-party.

### 6.4 Scan for Other Bundled Data Files

Check for any other embedded binary data or assets that may constitute bundled
content:

```bash
rg -n 'include_bytes!|include_str!|include_dir!' goose-{TARGET_VERSION}/crates/ \
  -t rust --glob '!target/' | rg -v '\.md"' | rg -v '/prompts/'
```

Review any new `include_bytes!()` or `include_dir!()` calls that reference
third-party data files (e.g., model weights, filter banks, font files). Internal
project files (prompts, templates, configs) do not need `Provides: bundled()`
entries.

### 6.5 Update Spec Provides

After all scans, present a summary table to the user:

| Artifact | Current Spec Entry | Source Status | Action |
|----------|-------------------|---------------|--------|
| (each bundled item) | (existing entry or MISSING) | (found/removed/version changed) | (add/remove/update/keep) |

Apply the agreed changes to the `Provides: bundled()` section in `goose.spec`,
keeping the existing grouping and comment structure:
- Sublime syntax definitions grouped together with header comment
- Syntect themes grouped together with header comment
- JS/CSS libraries grouped together with header comment and per-file license

---

## Phase 7: License Audit

### 7.1 Check for New/Changed Licenses

Run `cargo license` from the extracted and patched source directory (with the
vendor tarball extracted in place) to get an early view of the license breakdown
before building:

```bash
cargo license --avoid-build-deps --avoid-dev-deps 2>/dev/null | sort | uniq -c | sort -rn
```

Compare the output against the current license list in the spec file comment
block (the block above the `License:` field). Note any new licenses or crates
that changed license.

After building, the `%{cargo_license_summary}` macro outputs the authoritative
license breakdown. Use the `cargo license` results as a preemptive check to
catch issues early, then confirm with `%{cargo_license_summary}` output after
the build.

### 7.2 Problematic License Check

Cross-reference every license found in 7.1 against both lists. Flag any crate
whose license:
- Appears on the **not-allowed** list — the crate MUST be removed or replaced
- Does not appear on the **approved** list — needs Fedora legal review before
  the package can ship
- Is not a valid SPDX identifier — needs correction

**Known licenses requiring special attention in this package:**
- `CC0-1.0` — Listed as "allowed" in Fedora but requires individual legal
  review per crate. The crate `constant_time_eq` was already approved (see
  legal ML thread in spec comments). New CC0-1.0 crates need separate legal
  approval.
- `GPL-2.0` (without `-only` or `-or-later`) — Invalid SPDX, needs correction
  to `GPL-2.0-only` or `GPL-2.0-or-later`
- `AGPL-*` — Check the not-allowed list; may cause distribution concerns
- `SSPL-*` — Not allowed in Fedora
- `BUSL-*` — Not allowed in Fedora
- Any unknown or custom license identifiers

Per Fedora Rust packaging guidelines, the License tag must cover all code
compiled into the final binary, including all vendored crates.

### 7.3 Update License Field

If the license list changed, update the `License:` field in the spec. The field
uses `%{shrink:}` macro and must be a valid SPDX expression. Follow this format:

- Each unique license combination gets its own line
- Use parentheses for OR combinations
- AND between each line (they're all compiled into the binary)
- Keep sorted alphabetically

Also update the comment block above the License field that lists the raw
`%{cargo_license_summary}` output for easy diffing on future updates.

### 7.4 Bundled JS/CSS License Files

If Phase 6.3 found version changes in the minified JavaScript/CSS files:
- Check if upstream merged the license files PR
  (https://github.com/aaif-goose/goose/pull/7352)
  - If merged, the separate Source2-Source7 license files may no longer be needed
  - If not merged, keep them and check if they need updating for the new versions

---

## Phase 8: Spec File Updates

### 8.1 Binary Targets

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

### 8.2 BuildRequires

Verify all BuildRequires are still correct. Phase 5.2 handles adding/removing
BuildRequires for `-sys` crates specifically — this step is for everything else.

Check that:
- Each BuildRequires has an inline comment explaining which vendored crate or
  feature needs it
- `pkgconfig()` dependencies are used where available (per Fedora guidelines)
- System library packages use `-devel` variants
- `cargo-rpm-macros >= 25` is present (required for vendored builds)
- No BuildRequires remain for `-sys` crates that were dropped in Phase 5.2.1

### 8.3 Test Skips

Review the `%check` section. Skipped tests may need updating if:
- Test function names changed upstream
- Tests were removed upstream (remove skip)
- New tests need skipping (network/DNS tests, tests requiring specific
  resources, tests with potential copyrightable content)

Each test skip must have a comment explaining the category of skip reason.

### 8.4 %prep Section

Verify these cleanup operations still reference valid paths:
- `documentation/` folder removal (keep only `static/img/logo_{dark,light}.png`)
- `ui/` folder removal (Electron desktop app)
- `bin/` folder removal (hermit bootstrap tools)
- `services/` folder removal (Discord bot)
- `test_image.jpg` removal (unclear copyright)

If upstream reorganized their directory structure, update these paths.

### 8.5 Vendored Crate Workarounds in %prep

Check if these workarounds in `%prep` are still needed:

1. **posthog-rs reqwest version pin**: Check if
   https://github.com/PostHog/posthog-rs/pull/55 was merged. If the new goose
   version uses the updated posthog-rs, remove the sed workaround.

2. **zstd pkg-config feature injection**: Check if upstream zstd-sys crate now
   includes `pkg-config` in default features. If so, remove the sed workaround.

3. **Cargo checksum clearing**: Any `prune_vendor` or sed workaround that
   modifies vendored crate files must also patch `.cargo-checksum.json`.

### 8.6 Source and Patch Declarations

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

---

## Phase 9: Bugzilla Compliance Checklist (BZ#2428704)

Before declaring the update ready, verify ALL of these. Present to user as
PASS/FAIL:

### Package Identity
- [ ] Package name is `goose` (not `rust-goose`)
- [ ] `Conflicts: golang-github-pressly-goose` is present
- [ ] `ExcludeArch: %{ix86}` is present

### Build System
- [ ] `BuildRequires: cargo-rpm-macros >= 25` (minimum for vendored builds)
- [ ] `%constrain_build` macro is present (prevents OOM on builders)
- [ ] `%cargo_prep -v vendor` used in `%prep`
- [ ] `%cargo_build` used in `%build`
- [ ] `%cargo_vendor_manifest` called in `%build`
- [ ] `%{cargo_license_summary}` called in `%build`
- [ ] `%{cargo_license} > LICENSE.dependencies` called in `%build`
- [ ] `%cargo_test` used in `%check`
- [ ] `%cargo_generate_buildrequires` NOT used (forbidden with vendored builds)

### System Libraries
(Only check crates still present after Phase 5.2.1 — skip any that were dropped)
- [ ] `bzip2-sys` pruned, `pkgconfig(bzip2)` in BuildRequires
- [ ] `libdbus-sys` pruned, `dbus-devel` in BuildRequires
- [ ] `libsqlite3-sys` pruned, `pkgconfig(sqlite3)` in BuildRequires
- [ ] `onig_sys` pruned, `oniguruma-devel` in BuildRequires
- [ ] `ring` pregenerated objects stripped via `prune_vendor`
- [ ] `zstd-sys` pruned, `libzstd-devel` in BuildRequires
- [ ] `RUSTONIG_SYSTEM_LIBONIG=1` set in BOTH `%build` and `%check`
- [ ] Any new `-sys` crates from Phase 5.2.2 have `prune_vendor` + BuildRequires

### Forbidden Content
- [ ] No `aws-lc` / `aws-lc-rs` crates in vendor tarball
- [ ] No `rustls` crate in vendor tarball (all TLS via native-tls/OpenSSL)
- [ ] No prebuilt `.o` / `.a` / `.so` / `.dll` files in vendor tarball
  (outside of directories handled by `prune_vendor`)
- [ ] No executable `.rs` files (chmod fix in `%prep`)

### Licensing
- [ ] License tag is valid SPDX expression
- [ ] All bundled JS/CSS have license files (Source2-Source7 or upstream)
- [ ] `cargo-vendor.txt` listed as `%license` in `%files`
- [ ] `LICENSE.dependencies` listed as `%license` in `%files`
- [ ] All `Provides: bundled()` entries present and versioned

### Content Cleanup
- [ ] `generate-vendor-tarball.sh` included as Source99
- [ ] `%prep` removes `documentation/` (keeps logo images)
- [ ] `%prep` removes `ui/` (Electron app)
- [ ] `%prep` removes `bin/` (hermit tools)
- [ ] `%prep` removes `services/` (Discord bot)
- [ ] `%prep` removes `test_image.jpg` (unclear copyright)

### Platform Conditionals
- [ ] RHEL-conditional patches properly gated (`%if 0%{?rhel}`)
- [ ] EPEL 9 sqlite requirement present
  (`Requires: sqlite-libs >= 3.34.1-10`)

---

## Phase 10: Build Verification

### 10.1 Local SRPM Build

```bash
fedpkg srpm
```

Verify the SRPM builds without errors. This is a basic sanity check — it
validates that the spec parses correctly, all Source/Patch files exist, and
`%prep` completes. The full build verification happens via Packit/COPR in the
next step.

### 10.2 Changelog

The spec uses `%autochangelog` — do NOT manually edit the changelog. The
changelog is auto-generated from git commit messages by `rpmautospec` at build
time. Ensure the commit message for this update is descriptive (e.g.,
"Update to version {TARGET_VERSION}").

### 10.3 Suggest Next Steps

After all phases complete, tell the user:

1. **Review the changes** with `git diff`
2. **Create a PR branch** and commit
3. **Push to trigger Packit** — Packit will run COPR builds on PR creation
   targeting all architectures and distribution versions listed in
   `.packit.yaml`
4. **After COPR passes**, the package is ready for fedpkg submission

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