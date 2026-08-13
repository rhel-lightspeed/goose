# Phase 5: License Audit

Verify all licenses are Fedora-approved and update the spec's License field.

All licenses MUST be valid SPDX identifiers from the Fedora approved license
list (see "Fedora Compliance References" in AGENTS.md).

Requires: Phase 4 completed, extracted and patched source with vendor in place.

---

## 5.1 Generate License Summary

Run `cargo2rpm` from the extracted source directory (with dependency patches
applied and vendor in place) to get the authoritative license breakdown — the
same output that `%{cargo_license_summary}` produces during the RPM build:

```bash
cd goose-{TARGET_VERSION}
cargo2rpm --path Cargo.toml license-summary
```

This outputs a block like:

```
### BEGIN LICENSE SUMMARY ###
# Apache-2.0 OR MIT
# BSD-3-Clause
# MIT
...
###  END LICENSE SUMMARY  ###
```

Compare this output against the existing comment block above the `License:`
field in `goose.spec` (the block starting with
`# output of %%{cargo_license_summary}`). Note:
- New license entries added
- License entries removed
- Changes in license expressions for existing crates

If the comment block changed, update it in the spec to match the new
`cargo2rpm` output.

## 5.2 Problematic License Check

Cross-reference every license from 5.1 against both Fedora lists. Flag any
crate whose license:

- Appears on the **not-allowed** list — crate MUST be removed or replaced
- Does not appear on the **approved** list — needs Fedora legal review
- Is not a valid SPDX identifier — needs correction

**Known special cases:**
- `CC0-1.0` — Allowed but requires per-crate legal review. Check spec comments
  for previously approved crates. New CC0-1.0 crates need separate approval.
- `GPL-2.0` (without `-only`/`-or-later`) — Invalid SPDX, needs correction
- `AGPL-*`, `SSPL-*`, `BUSL-*` — Check the not-allowed list

## 5.3 Normalize and Update the License Field

If the license summary changed in 5.1, rebuild the `License:` field from the
updated comment block. This ensures the SPDX expression is canonically ordered
and in sync with the `cargo2rpm` output.

### 5.3.1 Extract the Comment Block

Read every `# <license>` line from the comment block above the `License:` field
(the block between the `# output of %%{cargo_license_summary}.` line and the
`License:` field).

### 5.3.2 Normalize Each Entry

For each entry, sort all license identifiers within every OR or AND expression
alphabetically to produce its canonical form:

| Raw (cargo2rpm output) | Canonical |
|---|---|
| `MIT OR Apache-2.0` | `Apache-2.0 OR MIT` |
| `0BSD OR MIT OR Apache-2.0` | `0BSD OR Apache-2.0 OR MIT` |
| `MIT AND BSD-3-Clause` | `BSD-3-Clause AND MIT` |
| `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT` | `Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR MIT` |

### 5.3.3 Deduplicate

After canonicalizing, discard any entry whose canonical form has already been
seen. Common sources of duplicates in cargo output:

- `Apache-2.0 OR MIT` and `MIT OR Apache-2.0` → keep one
- `BSD-3-Clause AND MIT` and `MIT AND BSD-3-Clause` → keep one
- Multiple word-order variants of the same triple → keep one

### 5.3.4 Classify Each Unique Entry

**Simple OR** — two or more licenses joined by OR; wrap in parens:
- `Apache-2.0 OR MIT` → `(Apache-2.0 OR MIT)`

**Simple AND** — two licenses both required; wrap in parens:
- `BSD-3-Clause AND MIT` → `(BSD-3-Clause AND MIT)`

> **Critical:** if cargo says AND, the License field must say AND. Never convert
> AND to OR — they carry different legal obligations.

**Standalone** — a single license identifier; no parens needed:
- `Apache-2.0`, `ISC`, `bzip2-1.0.6`

**Compound AND with OR sub-expression** — entries like
`(Apache-2.0 OR MIT) AND BSD-3-Clause`. Do **not** add these as compound terms;
their component licenses are already covered as separate entries. Discard after
confirming all components are present in the list.

### 5.3.5 Sort

Sort all entries by their inner expression text (strip outer parens for the sort
key) using strict ASCII byte order:

```
( < 0-9 < A-Z < a-z
```

Practical consequences:
- Entries starting with a digit (`0BSD`) sort before uppercase letters
- Entries starting with a lowercase letter (`bzip2-1.0.6`) sort **after** all
  uppercase entries
- Among entries sharing the same prefix, the shorter one sorts first:
  `Apache-2.0` → `Apache-2.0 AND ISC` → `Apache-2.0 OR ...`
- AND sorts before OR at the same prefix level (`A` < `O`)

### 5.3.6 Write the License Field

Replace the existing `License:` block with the sorted entries using the spec's
`%{shrink:}` pattern. The first entry has no `AND ` prefix; every subsequent
entry is prefixed with `AND `:

```
License:        %{shrink:
                (0BSD OR Apache-2.0 OR MIT)
                AND Apache-2.0
                AND (Apache-2.0 AND ISC)
                AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR CC0-1.0)
                ...
                AND Zlib
                AND bzip2-1.0.6
                }
```

### 5.3.7 Verify the License Field

Compare the new field against the old one and account for every difference:

- **Entry removed** — confirm no matching comment block entry exists
- **Entry added** — confirm it maps to a comment block entry
- **AND ↔ OR change** — always a substantive correction; note it explicitly
- **Reordered only** — cosmetic, no action needed

## 5.4 Bundled JS/CSS License Files

If Phase 4.3 found version changes in minified JS/CSS files, check whether
the upstream source includes license files for them:

```bash
# Search for license files near bundled JS/CSS
fd -t f 'LICENSE|COPYING|NOTICE' crates/ | sort
```

If license files exist in the source tree, the separate `Source` license
entries in the spec may no longer be needed. If not found, verify the
existing `Source` license files in the spec match the current library
versions.

## Verification

- [ ] `cargo2rpm license-summary` output matches the spec comment block
- [ ] All licenses in the summary are Fedora-approved SPDX identifiers
- [ ] No crate uses a not-allowed license
- [ ] `License:` field is a valid SPDX expression, canonically ordered
- [ ] Bundled JS/CSS have corresponding license files
- [ ] `cargo-vendor.txt` and `LICENSE.dependencies` in `%files` as `%license`
