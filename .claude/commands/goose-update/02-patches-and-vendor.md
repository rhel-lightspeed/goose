# Phase 2: Patches & Vendor Tarball

Test all patches, rebase as needed, generate the vendor tarball, then test
vendor patches. This phase handles the full patch lifecycle in one pass.

Requires: Phase 1 completed (source extracted in `goose-{TARGET_VERSION}/`).

---

## 2.1 Test Non-Vendor Patches

Test dependency, code, and RHEL-only patches against the extracted source.
Skip vendor patches (01xx) — they need the vendor tarball which doesn't exist
yet.

```bash
cd goose-{TARGET_VERSION}
for p in ../0*.patch; do
  case "$(basename "$p")" in 01[0-9][0-9]-*) continue;; esac
  echo "=== Testing: $(basename "$p")"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

## 2.2 Classify and Rebase

For each patch, read its header/subject to understand its purpose, then
classify based on the dry-run result:

1. **Applies cleanly** — Keep as-is
2. **Applies with fuzz/offset** — Rebase (regenerate the patch)
3. **Fails** — Read the patch to identify what lines it changes, then check
   those files in the new source with `rg` to see if the change is already
   present. If the upstream file already contains the patched content: drop
   the patch and remove from spec. If the change is still needed but context
   shifted: rebase manually using the `.orig` pattern.
4. **No longer relevant** — If the target files no longer exist or the code
   changed so the patch is moot, STOP and ask the user to confirm before
   dropping it and removing the `Patch:` tag from the spec. Do not drop a
   patch silently.

For CVE patches (`0xxx-Fix-for-CVE-*`), read the patch to identify the
vulnerable crate and version, then check the new `Cargo.lock`:

```bash
# Example: if the CVE patch fixes crate "foo" version 1.2.3
rg '^name = "foo"' -A 1 goose-{TARGET_VERSION}/Cargo.lock
```

If the crate version in the new `Cargo.lock` is newer than the patched
version, the fix was likely included upstream — drop the patch.

## 2.3 Regenerate Failed Patches

For each patch that needs rebasing:

1. Read the failing patch to understand what changes it makes
2. For each changed line in the patch, use `rg` to check whether the
   upstream file still has the original (unpatched) content. If the upstream
   already matches the patched version, that hunk is no longer needed.
3. Apply changes manually using the `.orig` pattern:

   ```bash
   cp path/to/Cargo.toml path/to/Cargo.toml.orig
   # ... make the same changes to path/to/Cargo.toml ...
   ```

4. Generate the new patch:

   ```bash
   fd -t f '\.orig$' . | sort | while read orig; do
     modified="${orig%.orig}"
     rel="${modified#./}"
     diff -u --label "a/$rel" --label "b/$rel" "$orig" "$modified"
   done > ../NNNN-Patch-description.patch
   ```

5. Clean up `.orig` files before working on the next patch:
   ```bash
   fd -t f '\.orig$' . -x rm
   ```

**Important:** Do not add feature-flag changes to dependency patches — feature
selection is handled at build time (see "Downstream Feature Flags" in
AGENTS.md).

## 2.4 Update and Run Vendor Tarball Script

Read `generate-vendor-tarball.sh` and verify its `PATCHES` array lists exactly
the dependency patches (0000-0099 range) currently in the repo:

```bash
# Patches the script expects
rg -A 20 '^PATCHES=\(' generate-vendor-tarball.sh | rg '\.patch'

# Dependency patches that exist
ls 00[0-9][0-9]-*.patch 2>/dev/null
```

If patches were added, removed, or renamed in 2.2/2.3, update the array.

Also verify the feature flags in the `cargo vendor-filterer` call match the
spec's `%{downstream_features}` macro:

```bash
rg -A 3 'vendor-filterer' generate-vendor-tarball.sh | rg 'features'
rg 'downstream_features' goose.spec
```

Generate the vendor tarball:

```bash
./generate-vendor-tarball.sh
```

## 2.5 Test Vendor Patches (0100 series)

Now that the vendor tarball exists, test vendor-targeting patches:

```bash
cd goose-{TARGET_VERSION}
tar xf ../goose-{TARGET_VERSION}-vendor.tar.xz
for p in ../01[0-9][0-9]-*.patch; do
  [ -f "$p" ] || continue
  echo "=== Testing: $(basename "$p")"
  patch -p1 --dry-run < "$p" && echo "OK" || echo "FAILED"
done
```

If a vendor patch fails, check whether the target crate version changed (the
patch path includes the crate version, e.g., `vendor/ring-0.17.8/build.rs`).
If so, regenerate with the updated path using the `.orig` pattern.

## Verification

After all patches are handled:

- [ ] Every patch in the repo applies cleanly with `patch -p1 --dry-run`
- [ ] Dropped patches removed from both repo and spec `Patch:` tags
- [ ] Dependency patches (0000-0099) match `PATCHES` array in vendor script
- [ ] Feature flags match between vendor script and spec
- [ ] Vendor tarball generated successfully
- [ ] Vendor patches (0100+) apply cleanly against vendor tarball
