# Phase 6: Spec File Updates

Update all remaining spec file sections affected by the version change.

Requires: Phases 3-5 completed (compliance, bundled content, and licenses
handled).

---

## 6.1 Binary Targets

Check if new binary targets were added upstream:

```bash
rg '^\[\[bin\]\]' goose-{TARGET_VERSION}/Cargo.toml \
  goose-{TARGET_VERSION}/crates/*/Cargo.toml
```

Compare against the `%install` and `%files` sections in the spec. Add any new
binaries.

### 6.1.1 Man Pages

Verify the man page generator still exists and is wired up:

```bash
# Check generator binary target exists
rg -A 5 'generate_manpages' goose-{TARGET_VERSION}/crates/goose-cli/Cargo.toml

# Check spec builds and installs man pages
rg 'generate_manpages' goose.spec
rg 'mandir' goose.spec
```

## 6.2 BuildRequires

Verify all `BuildRequires` are still correct. Phase 3.2 handles `-sys` crate
requirements — this step covers everything else.

```bash
# List all BuildRequires with their comments
rg '^BuildRequires:' goose.spec
```

Check that:
- Each `BuildRequires` has an inline comment explaining why it's needed
- `pkgconfig()` dependencies are used where available
- `cargo-rpm-macros >= 25` is present
- No stale entries for dropped crates remain

## 6.3 Test Skips

Review the `%check` section for test skips:

```bash
sed -n '/%check/,/%files/p' goose.spec | rg -i 'skip|ignore'
```

For each skipped test function name, verify it still exists in the source:

```bash
# Extract test function names from skip patterns in %check
sed -n '/%check/,/%files/p' goose.spec | rg -o '[a-z_]+::[a-z_]+' | while read test; do
  if rg -q "$test" goose-{TARGET_VERSION}/crates/; then
    echo "KEEP skip: $test still exists"
  else
    echo "DROP skip: $test no longer exists"
  fi
done
```

Each skip must have a comment explaining the reason.

## 6.4 %prep Content Cleanup

The `%prep` section removes upstream directories not needed for packaging.
Extract the list of removed paths from the spec and verify each still exists:

```bash
# Extract directory removals from %prep
sed -n '/%prep/,/%build/p' goose.spec | rg 'rm -rf' | rg -o '%{_builddir}/\S+' | \
  sed "s|%{_builddir}/%{name}-%{version}/||"

# For each path found above, check if it exists in the new source
for dir in $(sed -n '/%prep/,/%build/p' goose.spec | rg 'rm -rf' | \
  rg -o '[a-zA-Z_][a-zA-Z0-9_/]*/' | sort -u); do
  dir="${dir%/}"
  if [ -d "goose-{TARGET_VERSION}/$dir" ]; then
    echo "KEEP removal: $dir exists"
  else
    echo "DROP removal: $dir no longer exists"
  fi
done
```

Remove cleanup commands for directories that no longer exist. Add cleanup
for any new directories that should not be shipped — scan for large non-Rust
content:

```bash
# Find top-level directories that aren't Rust source or packaging
ls -d goose-{TARGET_VERSION}/*/ | while read d; do
  name=$(basename "$d")
  case "$name" in crates|vendor|.cargo) continue;; esac
  echo "$name: $(fd -t f . "$d" | wc -l) files"
done
```

## 6.5 Vendored Crate Workarounds

The `%prep` section may contain `sed` commands that patch vendored crate
files. For each one, check if it's still needed:

```bash
# List all sed workarounds targeting vendor/
sed -n '/%prep/,/%build/p' goose.spec | rg 'sed.*vendor/'
```

For each workaround found:

1. Extract the target file path from the `sed` command
2. Check if the target file exists in the vendor tarball:
   ```bash
   ls vendor/{CRATE}-*/path/to/file 2>/dev/null
   ```
3. If the file exists, read it and check whether the line the `sed` modifies
   still contains the pattern being replaced:
   ```bash
   rg '{PATTERN_FROM_SED}' vendor/{CRATE}-*/path/to/file
   ```
   - If the pattern matches: workaround still needed, verify the crate
     version in the path is current
   - If no match: the upstream crate fixed the issue, remove the workaround
4. If the target file doesn't exist at all (crate was dropped or renamed),
   remove the workaround

Any `sed` that modifies a vendored crate file must also clear
`.cargo-checksum.json` for that crate. Verify each has a corresponding
checksum clear:

```bash
# For each crate modified by sed, check for checksum clearing
sed -n '/%prep/,/%build/p' goose.spec | rg 'sed.*vendor/' | \
  rg -o 'vendor/[^/]*' | sort -u | while read crate_dir; do
  if rg -q "cargo-checksum.*${crate_dir}" goose.spec; then
    echo "OK: checksum cleared for $crate_dir"
  else
    echo "MISSING: no checksum clear for $crate_dir"
  fi
done
```

## 6.6 Build-Time Feature Flags

Verify all three call sites use identical flags (see "Downstream Feature Flags"
in AGENTS.md for the full rule):

```bash
# Spec macro
rg '%global downstream_features' goose.spec

# %cargo_build
rg '%cargo_build' goose.spec

# %cargo_test
rg '%cargo_test' goose.spec

# generate-vendor-tarball.sh
rg -A 3 'vendor-filterer' generate-vendor-tarball.sh | rg 'features'
```

All three must specify the same feature set with `--no-default-features`.

## 6.7 Source and Patch Declarations

Verify the rules from AGENTS.md ("Source and Patch Declaration Rules"):

```bash
# All Source/Patch tags must be unconditional (not inside %if blocks)
awk '/%if/{d++} /%endif/{d--} d>0 && /^(Source|Patch)/' goose.spec

# Each Patch should have an explanatory comment
rg -B1 '^Patch' goose.spec
```

Verify new patches are assigned to the correct number range (see "Patch
Numbering Convention" in AGENTS.md).

## Verification

After this phase:

- [ ] All binary targets in spec match upstream `[[bin]]` sections
- [ ] Man page generation is wired up
- [ ] BuildRequires are current (no stale, no missing)
- [ ] Test skips are current (no stale, all have comments)
- [ ] `%prep` cleanup paths match the new source structure
- [ ] Vendored crate workarounds are still needed (or removed)
- [ ] Feature flags are identical across spec + vendor script
- [ ] All Source/Patch tags are unconditional with comments
