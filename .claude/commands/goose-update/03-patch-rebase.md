# Phase 3: Patch Rebase

This is the most critical phase. Test all existing patches against the new
source and rebase or drop as needed.

Requires: Phase 2 completed (new source tarball downloaded).

---

## Patch Series Structure

Patches are organized into three categories by purpose:

### Dependency patches (0000-0019) — Cargo.toml modifications

These modify `Cargo.toml` files across the workspace and affect dependency
resolution. They are listed in `generate-vendor-tarball.sh`'s `PATCHES` array
and applied both during vendor tarball generation and during the RPM build.

- `0000` — **Upstream dependency hygiene port** *(optional, only present when
  needed)*: Upgrades otel, removes git overrides from `[patch.crates-io]`, sets
  `default = []` on goose lib crate, puts nostr and sigstore-verify behind
  feature flags. Based on upstream PRs that haven't yet been released.
- `0001` — **Platform cleanup + system library linkage**: Removes Windows/macOS
  platform deps (winapi, winreg, metal, apple-native keyring), the vendor/v8
  workspace member, and all remaining `[patch.crates-io]` entries (v8,
  cudaforge). Removes the keyring `vendored` feature. Switches sqlx from
  bundled `sqlite` to `sqlite-unbundled` for system libsqlite3 linkage. Does
  NOT touch `[package.metadata.cargo-machete]` sections — those are
  development-only and irrelevant to packaging.
- `0002` — **aws-lc-rs feature gate**: Removes `aws_lc_rs` from the
  workspace-level rustls default features in the root `Cargo.toml`, then adds
  `rustls/aws_lc_rs` explicitly to the rustls-tls feature gate in
  `crates/goose/Cargo.toml`, so aws-lc-sys is not pulled in on the native-tls
  build path.

> **Note:** Feature flags (native-tls, otel, telemetry, system-keyring,
> disable-update) are **not** patched into Cargo.toml defaults. They are passed
> explicitly at build time via `--no-default-features --features ...` in both
> the spec (`%cargo_build`, `%cargo_test`) and in the vendor script
> (`cargo vendor-filterer`). This means the upstream default-features list is
> NOT a maintenance concern for packaging — only the feature definitions
> themselves need to survive rebases.
>
> Package scoping works the same way: do NOT patch `default-members` into the
> workspace `Cargo.toml`. `%cargo_build`/`%cargo_test` pass
> `-- --package goose-cli` instead (a literal `--` after the macro's own
> `-n -f` flags, since `%cargo_build`/`%cargo_test` have no `-p` short option
> and error with "Unknown option p" if you pass one directly — everything
> after `--` goes straight to the underlying `cargo` invocation). This scopes
> the build to `goose-cli` and its dependency tree. With `resolver = "2"`,
> building the whole workspace in one invocation activates `--features` names
> across every workspace member that defines them, which can leak forbidden
> deps (e.g. `aws-lc-rs`) in from crates goose-cli doesn't even depend on.

### Code patches (0020-0099) — Rust source code changes

These modify `.rs` files or test snapshots. They do NOT affect dependency
resolution and are NOT listed in the vendor tarball script.

- `0020` — EPEL 9 SQLite compatibility (avoids RETURNING statement)
- `0021` — Snapshot test update for code-mode being absent from build features

### Vendor patches (0100-0799) — Target vendored crates

Applied from the source root (paths start with `vendor/`):

- `0100` — Patch ring's build.rs to never use pre-generated object files
- `0101` — Add `default-features = false` to hf-hub's reqwest dependency. hf-hub
  is a workspace member dep (via goose-local-inference) that pulls reqwest without
  disabling defaults, activating default-tls → rustls → aws_lc_rs on the
  native-tls path. Check on each bump whether the upstream hf-hub release fixed
  this; if so, drop the patch.

### RHEL-only patches (0800-0899) — Conditional on `%if 0%{?rhel}`

- `0800` — Include legal disclaimer for goose proxy provider

## 3.1 Extract and Test Patches

Extract the new source and test each patch:

```bash
tar xf goose-{TARGET_VERSION}.tar.gz
cd goose-{TARGET_VERSION}
for p in ../0*.patch; do
  # Skip vendor (01xx) and RHEL-only (08xx) patches — tested in steps 3.5/3.6
  case "$(basename "$p")" in 01[0-9][0-9]-*|08[0-9][0-9]-*) continue;; esac
  echo "=== Testing: $p"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

## 3.2 Classify Patch Status

For each patch, determine:

1. **Applies cleanly** — Keep as-is
2. **Applies with fuzz/offset** — Rebase (re-generate the patch)
3. **Fails** — Check if the change was merged upstream:
   - If merged upstream: **drop the patch** and remove from spec
   - If not merged but context changed: **rebase manually**
4. **No longer relevant** — If the upstream code changed so the patch target
   no longer exists, investigate and report to user

## 3.3 Regenerate Dependency Patches (0001, 0002)

These patches modify `Cargo.toml` files across the workspace. When upstream
changes dependencies, they almost always need regenerating.

**Process to regenerate:**

1. Extract the new source into a temp directory and `git init`
2. For Patch 0001 (platform cleanup + system libraries): identify all
   Windows/macOS platform deps and `[patch.crates-io]` entries, remove them.
   Verify that sqlx still uses `sqlite-unbundled` (not `sqlite`). Do NOT
   touch `[package.metadata.cargo-machete]` sections, and do NOT add
   `default-members` — package scoping is a build flag
   (`-- --package goose-cli`), not a Cargo.toml patch.
3. For Patch 0002 (aws-lc-rs feature gate): verify that the workspace-level
   rustls dependency still hardcodes `aws_lc_rs` in its features list. If
   upstream removed it (or moved it behind a feature flag), drop the patch. Also
   check that `crates/goose/Cargo.toml`'s rustls-tls feature still needs the
   explicit `rustls/aws_lc_rs` activation.
4. Generate each patch with `git diff` after committing the previous one.

**CRITICAL:** Any patch that modifies `Cargo.toml` or `Cargo.lock` must be
listed in `generate-vendor-tarball.sh`'s `PATCHES` array because it affects
what gets vendored. Currently that is 0001 and 0002. If patches are added,
dropped, or renamed, update the `PATCHES` array too.

**Do NOT add feature-flag changes back to these patches.** Feature selection
(native-tls, otel, telemetry, system-keyring, disable-update) is handled
entirely at build time via `--no-default-features --features ...` in the spec
and in the vendor-filterer call. Modifying Cargo.toml default feature lists is
no longer part of the packaging workflow.

## 3.4 Check CVE Patches

For any `0xxx-Fix-for-CVE-*` patches:
- Check if the CVE was fixed in the target version's dependency tree
- If the vulnerable crate was updated upstream, the patch can likely be dropped
- If not, rebase the patch against the new version

## 3.5 Check Downstream-Only Patches

Patches like the legal disclaimer (0800) for RHEL-specific fixes should be
checked for applicability but are unlikely to conflict unless the affected files
changed significantly upstream.

## 3.6 Check Vendor Patches (0100 series)

**Note:** This step is deferred until after Phase 4 (vendor tarball generation),
since the vendor directory does not exist yet. Come back here after running
`generate-vendor-tarball.sh`.

Test vendor-targeting patches. These are applied from the source root (not
inside `vendor/`), as their paths already start with `vendor/`:

```bash
tar xf goose-{TARGET_VERSION}-vendor.tar.zstd
for p in ../0100*.patch ../0101*.patch; do
  [ -f "$p" ] || continue
  echo "=== Testing: $p"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

Check if `ring` crate version changed — if so, the patch path in 0100
(`vendor/ring-{VERSION}/build.rs`) needs updating.

Check if `hf-hub` version changed — if so, the patch path in 0101
(`vendor/hf-hub-{VERSION}/Cargo.toml`) needs updating. Also check whether
the new hf-hub release added `default-features = false` to its reqwest dep
upstream; if so, drop 0101 and remove the checksum-clearing block from the
spec.
