# Phase 4: Bundled Content Audit

Identify all non-crate artifacts embedded in the source or vendor tree that
must be declared as `Provides: bundled()` in the spec file.

Requires: Phase 3 completed (vendor tarball extracted and verified).

---

## 4.1 Scan for Bundled Sublime Syntax Definitions

The `syntect` crate bundles sublimehq/Packages syntax definitions as compiled
packdump files.

```bash
# Find syntect in vendor tree
ls -d vendor/syntect-*/

# Extract bundled language list
strings vendor/syntect-*/assets/default_newlines.packdump | rg 'Packages/' | sed 's|.*/||' | sort -u
```

Extract existing entries from the spec and compare:

```bash
rg 'Provides:.*bundled\(sublime-syntax' goose.spec | rg -o 'sublime-syntax-[^)]*' | sort
```

Report additions and removals.

Check the syntect crate version (from `vendor/syntect-*/Cargo.toml`) and update
the version in `Provides: bundled(sublime-syntax)` if it changed.

## 4.2 Scan for Bundled Syntect Themes

```bash
rg -A 20 'fn get_integrated_themeset|ThemeSet' vendor/syntect-*/src/dumps.rs 2>/dev/null || \
rg 'theme' vendor/syntect-*/assets/ 2>/dev/null
```

Extract existing theme entries from spec and compare:

```bash
rg 'Provides:.*bundled\(s.*theme' goose.spec
```

Report changes.

## 4.3 Scan for Bundled JavaScript and CSS Libraries

Scan all crates for minified third-party JS/CSS files:

```bash
# Find all JS/CSS files
fd -e js -e css -E target -E 'test*' . crates/ | sort

# Find minified files and show their headers for version identification
fd -e min.js -e min.css -E target -E 'test*' . crates/ \
  -x sh -c 'echo "=== {} ==="; head -5 "{}"; echo'
```

Extract existing JS/CSS bundled entries from the spec:

```bash
rg 'Provides:.*bundled\((js|css|npm)' goose.spec
```

Compare each file against the existing entries. Report:
- New files (need `Provides` with version)
- Removed files (drop stale `Provides`)
- Version changes (update `Provides`)
- Files where version could not be determined (flag for user)

Non-minified JS/CSS that appears to be project-internal code does not need
`Provides: bundled()` — only third-party libraries do. Flag ambiguous files
for the user to classify.

## 4.4 Scan for Other Bundled Data Files

Check for embedded binary data or assets:

```bash
rg -n 'include_bytes!|include_str!|include_dir!' crates/ \
  -t rust --glob '!target/' | rg -v '\.md"' | rg -v '/prompts/'
```

Review any new `include_bytes!()` or `include_dir!()` calls that reference
third-party data. Internal project files (prompts, templates, configs) do not
need `Provides: bundled()`.

## 4.5 Update Spec Provides

Present a summary table:

| Artifact | Current Spec Entry | Source Status | Action |
|----------|-------------------|---------------|--------|
| (each item) | (existing or MISSING) | (found/removed/changed) | (add/remove/update/keep) |

Apply agreed changes to the `Provides: bundled()` section, keeping the
existing grouping and comment structure.

## Verification

- [ ] Every third-party bundled artifact has a versioned `Provides: bundled()`
- [ ] No stale `Provides` entries for removed artifacts
- [ ] Versions match what's actually in the source/vendor tree
