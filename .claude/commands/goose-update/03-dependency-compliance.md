# Phase 3: Dependency Compliance Audit

Enforce the rules from the Fedora package review (BZ#2428704).

Requires: Phase 2 completed (vendor tarball generated), dependency patches
applied to the extracted source, and vendor tarball extracted in place.

---

## 3.1 Forbidden Crates Check

Verify these crates are NOT in the dependency tree:

| Crate | Rule |
|-------|------|
| `rustls` | All TLS must go through `native-tls` (OpenSSL) |
| `aws-lc-rs` / `aws-lc-sys` | Forbidden entirely — must not exist in the dependency tree or vendor tarball |
| `ring` | Allowed, but `pregenerated/` directory MUST be stripped and build.rs patched to never use pre-generated objects |

The authoritative check is `cargo tree` with the downstream feature flags,
run from the extracted source directory with vendor in place. This verifies
the crates are not reachable in the actual build configuration:

```bash
# Read the downstream feature set from the spec
FEATURES=$(rg '%global downstream_features' goose.spec | awk '{print $NF}')
if [ -z "$FEATURES" ]; then
  echo "FAIL: could not read %{downstream_features} from goose.spec — stop, do not continue with an empty feature set"
  exit 1
fi
echo "downstream_features: $FEATURES"

for crate in rustls aws-lc-rs aws-lc-sys; do
  echo "=== Checking: $crate ==="
  cargo tree --no-default-features --features "$FEATURES" -i "$crate" 2>&1
  if [ $? -eq 0 ]; then
    echo "FAIL: $crate is in the dependency tree"
  else
    echo "OK: $crate not reachable"
  fi
done
```

Also verify the crates are not present in the vendor tarball at all (even
unreachable crates in the vendor tree are a compliance concern):

```bash
for crate in rustls aws-lc-rs aws-lc-sys; do
  if ls -d vendor/${crate}-*/ >/dev/null 2>&1; then
    echo "FAIL: ${crate} found in vendor tree"
  else
    echo "OK: ${crate} not vendored"
  fi
done
```

If any forbidden crate is present, it means the crate is reachable even with
`%{downstream_features}` applied — some crate pulls it in unconditionally.
Go back to Phase 2 and add/fix a dependency patch (0000-0099) targeting that
specific unconditional path (see "Do not patch Cargo.toml just to 'turn off'
a feature" in AGENTS.md for the exact pattern, e.g.
`0004-aws-lc-rs-feature-flag.patch`). Do **not** change `%{downstream_features}`
or the feature list at the build call sites to work around this — that macro
is a single source of truth shared across `%build`, `%check`, and the vendor
script (see Phase 6.6).

## 3.2 System Library Linkage Verification

Vendored `-sys` crates that bundle C libraries MUST link against system
libraries instead. This section discovers which `-sys` crates are present and
verifies each one is handled correctly.

### 3.2.1 Discover -sys crates in vendor tree

Scan for `-sys` crates whose `build.rs` compiles C code or uses pkg-config:

```bash
fd -t f 'build\.rs' vendor/ -d 3 \
  | rg -- '-sys-' \
  | xargs rg -l 'cc::Build|pkg_config|cmake::Config|bindgen::Builder'
```

Also check for non `-sys` crates that bundle C source (e.g., `ring`):

```bash
fd -t f 'build\.rs' vendor/ -d 3 \
  | xargs rg -l 'cc::Build|pkg_config|cmake::Config|bindgen::Builder'
```

### 3.2.2 Cross-reference against spec

For each crate found in 3.2.1, check whether the spec's `%prep` section
already has a `prune_vendor` call or equivalent cleanup for it:

```bash
rg -o 'prune_vendor "[^"]*"' goose.spec | sort
```

Classify each crate as:

1. **Already handled** — `prune_vendor` exists, `BuildRequires` present. Verify
   the pruned directory still matches (crate versions change).
2. **New crate** — Not in spec. Needs investigation:
   - Identify bundled C source directories inside the crate
   - Check for a Fedora system package: `dnf provides 'pkgconfig({LIBRARY})'`
     or `dnf search {LIBRARY}-devel`
   - If system package exists: add `prune_vendor` + `BuildRequires`
   - If not: check whether it contains prebuilt objects (see 3.3). If it does
     not compile bundled C source and does not contain prebuilt objects, no
     action is needed. If it does either and no system package exists, STOP
     and present the crate/library name to the user — packaging a new system
     library dependency is a policy decision, not something to resolve
     unilaterally.
3. **Stale entry** — `prune_vendor` exists in spec but crate is no longer in
   vendor tree. Remove the `prune_vendor` call and corresponding `BuildRequires`.

For new crates that need system library linkage, check the crate's `build.rs`
for environment variable toggles (like `RUSTONIG_SYSTEM_LIBONIG=1`) and add
them to both `%build` and `%check` if needed.

### 3.2.3 Check for default-features bypass

The `%prep` section may inject features (e.g., `pkg-config`) into the
`default` feature list of certain vendored crates so they use system libraries.
If an intermediate crate depends on the target with `default-features = false`,
those injected defaults are silently ignored.

For every crate where `%prep` injects features into `default = [...]`, search
for dependents that disable defaults:

```bash
# Read the spec to find which crates have feature injection
rg -B2 -A2 'default.*=.*\[' goose.spec | rg -o 'vendor/[^/]*'

# For each such crate, check dependents
for crate in {CRATE_NAMES}; do
  rg -l "\[dependencies\.${crate}\]" vendor/*/Cargo.toml 2>/dev/null | while read f; do
    if sed -n "/\[dependencies\.${crate}\]/,/^\[/p" "$f" | rg -q 'default-features = false'; then
      echo "WARNING: $f disables default-features for ${crate}"
      sed -n "/\[dependencies\.${crate}\]/,/^\[/p" "$f" | rg '(features|default-features)'
    fi
  done
done
```

For each WARNING, verify the injected feature is explicitly listed in the
dependency's `features = [...]`. If not, add a `sed` command in `%prep` to
inject it, and ensure `.cargo-checksum.json` is cleared for the patched crate.

## 3.3 Prebuilt Object/Binary Scan

Scan for prebuilt objects or binaries in the vendor tarball:

```bash
fd -e o -e a -e so -e dll -e lib -e dylib . vendor/ | head -50
```

If any are found outside directories already handled by `prune_vendor`, they
must be addressed per Fedora guidelines (no prebuilt binaries in source
packages).

## Verification

After this phase:

- [ ] No forbidden crates (rustls, aws-lc-rs, aws-lc-sys) in vendor tree
- [ ] Every `-sys` crate that bundles C source has a `prune_vendor` call and
  corresponding `BuildRequires` in the spec
- [ ] No stale `prune_vendor` entries for crates no longer in vendor tree
- [ ] No prebuilt `.o`/`.a`/`.so` files outside pruned directories
- [ ] Feature injection in `%prep` is not bypassed by `default-features = false`
