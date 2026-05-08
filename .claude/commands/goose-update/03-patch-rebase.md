# Phase 3: Patch Rebase

This is the most critical phase. Test all existing patches against the new
source and rebase or drop as needed.

Requires: Phase 2 completed (new source tarball downloaded).

---

## Patch Series Structure

Patches are organized into three categories by purpose:

### Dependency patches (0000-0002) — Cargo.toml modifications

These modify `Cargo.toml` files across the workspace and affect dependency
resolution. They are listed in `generate-vendor-tarball.sh`'s `PATCHES` array
and applied both during vendor tarball generation and during the RPM build.

- `0000` — **Upstream dependency hygiene port**: Upgrades otel, removes git
  overrides from `[patch.crates-io]`, sets `default = []` on goose lib crate,
  puts nostr and sigstore-verify behind feature flags. Based on upstream PRs
  that haven't yet been released.
- `0001` — **Platform cleanup**: Removes Windows/macOS platform deps (winapi,
  winreg, metal, apple-native keyring), the vendor/v8 workspace member, and
  all remaining `[patch.crates-io]` entries (v8, cudaforge). Also removes the
  keyring `vendored` feature. Does NOT touch `[package.metadata.cargo-machete]`
  sections — those are development-only and irrelevant to packaging.
- `0002` — **Feature flags**: Sets downstream default features to
  `aws-providers`, `native-tls`, `telemetry`, `otel`, `system-keyring` in
  goose-cli and goose-server. Disables default features for jsonschema, config,
  and aws-config. Switches sqlx to `sqlite-unbundled`.

### Code patches (0003-0099) — Rust source code changes

These modify `.rs` files or test snapshots. They do NOT affect dependency
resolution and are NOT listed in the vendor tarball script.

- `0003` — EPEL 9 SQLite compatibility (avoids RETURNING statement)
- `0004` — Snapshot test update for disabled code-mode

### Vendor patches (0100-0799) — Target vendored crates

Applied from the source root (paths start with `vendor/`):

- `0100` — Patch ring's build.rs to never use pre-generated object files

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

## 3.3 Regenerate Dependency Patches (0000, 0001, 0002)

These patches modify `Cargo.toml` files across the workspace. When upstream
changes dependencies, they almost always need regenerating.

**Process to regenerate:**

1. Extract the new source into a temp directory and `git init`
2. For Patch 0000 (upstream port): check if the upstream PRs it ports have
   been merged into the new release. If so, the patch can be dropped. If not,
   apply the same logical changes (otel upgrade, git-patch removal, feature
   gating) to the new source.
3. For Patch 0001 (platform cleanup): identify all Windows/macOS platform deps
   and `[patch.crates-io]` entries, remove them. Do NOT touch
   `[package.metadata.cargo-machete]` sections.
4. For Patch 0002 (feature flags): set default features in goose-cli and
   goose-server to: `aws-providers`, `native-tls`, `telemetry`, `otel`,
   `system-keyring`. Disable default features for jsonschema, config,
   aws-config. Switch sqlx to `sqlite-unbundled`.
5. Generate each patch with `git diff` after committing the previous one.

**CRITICAL:** Patches 0000, 0001, and 0002 are listed in
`generate-vendor-tarball.sh`'s `PATCHES` array because they affect
`Cargo.toml`/`Cargo.lock` which changes what gets vendored. If these patches
change, update the `PATCHES` array in that script too.

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
tar xf goose-{TARGET_VERSION}-vendor.tar.xz
for p in ../0100*.patch ../0101*.patch; do
  [ -f "$p" ] || continue
  echo "=== Testing: $p"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

Check if `ring` crate version changed — if so, the patch path in 0100
(`vendor/ring-{VERSION}/build.rs`) needs updating.
