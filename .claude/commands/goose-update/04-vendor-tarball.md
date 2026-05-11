# Phase 4: Vendor Tarball Generation

Update the vendor tarball generation script and produce the new tarball.

Requires: Phase 3 completed (patches rebased). After this phase, return to
Phase 3.6 to test vendor-targeting patches.

---

## 4.1 Update generate-vendor-tarball.sh

Check the `PATCHES` array in `generate-vendor-tarball.sh`. It must list exactly
the patches that modify `Cargo.toml` or `Cargo.lock` (affecting dependency
resolution). Currently these are (verify against the actual file):

- `0000-Patch-windows-dependencies-across-workspace.patch`
- `0001-Disable-rustls-and-default-features-for-some-librari.patch`
- CVE patches that update vendored crate versions (e.g., `0003-Fix-for-CVE-*`)

If patches were added, removed, or renamed in Phase 3, update this array.

## 4.2 Generate Vendor Tarball

```bash
./generate-vendor-tarball.sh
```

After the vendor tarball is generated, go back to Phase 3.6 to test
vendor-targeting patches (0100 series) against the new vendor directory.
