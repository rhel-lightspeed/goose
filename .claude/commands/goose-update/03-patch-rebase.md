# Phase 3: Patch Rebase

This is the most critical phase. Test all existing patches against the new
source and rebase or drop as needed.

Requires: Phase 2 completed (new source tarball downloaded).

---

## Patch Series Structure

**0000-0099 patches** — Applied to the goose source tree:
- `0000` — Remove Windows-specific dependencies (winapi/winreg) from Cargo.toml
  files across the workspace
- `0001` — Disable rustls and default features for dependencies, switch to
  native-tls in Cargo.toml
- `0002` — Patch Rust source code to use native-tls instead of rustls (separate
  from 0001 so Cargo.toml patches can be regenerated independently)
- `0003+` — CVE fixes, downstream-only fixes

**0100-0799 patches** — Target vendored crates (paths start with `vendor/`,
applied from the source root via `%autopatch -p1 -M 799`):
- `0100` — Patch ring's build.rs to never use pre-generated object files
- `0101` — Raise recursion limit for packaging

**0800-0899 patches** — RHEL-only (applied conditionally in `%prep` via
`%autopatch -p1 -m 800 -M 899` inside `%if 0%{?rhel}`):
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

## 3.3 Regenerate Dependency Patches (0000 and 0001)

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
