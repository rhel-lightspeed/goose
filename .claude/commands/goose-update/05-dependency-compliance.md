# Phase 5: Dependency Compliance Audit

This phase enforces the rules from the Fedora package review (BZ#2428704).

Requires: Phase 4 completed (vendor tarball generated), patches 0000-0002
applied to the extracted source, and vendor tarball extracted in place.

---

## 5.1 Forbidden Crates Check

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

## 5.2 System Library Linkage Verification

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

### 5.2.1 Check if existing -sys crates are still needed

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

### 5.2.2 Check for new -sys crates

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

## 5.3 Prebuilt Object/Binary Scan

Scan for any prebuilt objects or binaries in the vendor tarball:

```bash
find vendor/ -name '*.o' -o -name '*.a' -o -name '*.so' -o -name '*.dll' -o -name '*.lib' -o -name '*.dylib' | head -50
```

If any are found outside of directories already handled by `prune_vendor`, they
must be addressed per Fedora packaging guidelines (no prebuilt binaries allowed
in source packages).
