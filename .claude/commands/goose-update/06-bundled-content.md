# Phase 6: Bundled Content Audit

This phase identifies all non-crate artifacts embedded in the source or vendor
tree that must be declared as `Provides: bundled()` in the spec file. Fedora
packaging guidelines require every bundled library or dataset shipped inside the
package to have a corresponding `Provides: bundled()` entry.

Requires: Phase 5 completed (vendor tarball extracted and verified).

---

## 6.1 Scan for Bundled Sublime Syntax Definitions

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

## 6.2 Scan for Bundled Syntect Themes

The `syntect` crate also bundles default color themes in its `assets/` directory.

1. Check the theme list in `vendor/syntect-*/src/dumps.rs` (look for
   `add_from_folder` or theme loading code):

```bash
grep -A 20 'fn get_integrated_themeset\|ThemeSet' vendor/syntect-*/src/dumps.rs 2>/dev/null || \
grep -r 'theme' vendor/syntect-*/assets/ 2>/dev/null
```

2. Compare against existing `Provides: bundled(syntect-theme-*)` and
   `Provides: bundled(sublime-theme-*)` entries in the spec. Report any changes.

## 6.3 Scan for Bundled JavaScript and CSS Libraries

Scan the entire source tree for minified third-party JavaScript and CSS files.
Currently the `goose-mcp` crate bundles libraries for the autovisualizer, but
new crates may also embed JS/CSS assets.

1. Find all `.js` and `.css` files across all crates (excluding test folders):

```bash
find crates/ \( -name '*.min.js' -o -name '*.min.css' -o -name '*.js' -o -name '*.css' \) \
  -not -path '*/target/*' -not -path '*/test*/*' | sort
```

2. For each minified file found, try to identify the library name and version
   by inspecting the file header or first few lines:

```bash
find crates/ \( -name '*.min.js' -o -name '*.min.css' \) \
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

## 6.4 Scan for Other Bundled Data Files

Check for any other embedded binary data or assets that may constitute bundled
content:

```bash
rg -n 'include_bytes!|include_str!|include_dir!' crates/ \
  -t rust --glob '!target/' | rg -v '\.md"' | rg -v '/prompts/'
```

Review any new `include_bytes!()` or `include_dir!()` calls that reference
third-party data files (e.g., model weights, filter banks, font files). Internal
project files (prompts, templates, configs) do not need `Provides: bundled()`
entries.

## 6.5 Update Spec Provides

After all scans, present a summary table to the user:

| Artifact | Current Spec Entry | Source Status | Action |
|----------|-------------------|---------------|--------|
| (each bundled item) | (existing entry or MISSING) | (found/removed/version changed) | (add/remove/update/keep) |

Apply the agreed changes to the `Provides: bundled()` section in `goose.spec`,
keeping the existing grouping and comment structure:
- Sublime syntax definitions grouped together with header comment
- Syntect themes grouped together with header comment
- JS/CSS libraries grouped together with header comment and per-file license
