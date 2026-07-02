# Normalize the License Field

Rebuild the `License:` field in the spec file from the `%{cargo_license_summary}`
comment block so both are in sync and the SPDX expression is canonically ordered.

Run this any time the comment block has been updated with fresh `cargo license
--summary` output, or when the License field and comment block have drifted apart.

---

## Step 1: Extract the Comment Block

Read every `# <license>` line from the comment block above the `License:` field
(the block between the `# output of %%{cargo_license_summary}.` line and the
`License:` field).

## Step 2: Normalize Each Entry

For each entry, sort all license identifiers within every OR or AND expression
alphabetically to produce its canonical form:

| Raw (cargo output)                                         | Canonical                                                  |
|------------------------------------------------------------|------------------------------------------------------------|
| `MIT OR Apache-2.0`                                        | `Apache-2.0 OR MIT`                                        |
| `0BSD OR MIT OR Apache-2.0`                                | `0BSD OR Apache-2.0 OR MIT`                                |
| `MIT OR Zlib OR Apache-2.0`                                | `Apache-2.0 OR MIT OR Zlib`                                |
| `MIT AND BSD-3-Clause`                                     | `BSD-3-Clause AND MIT`                                     |
| `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`     | `Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR MIT`      |
| `CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception` | `Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR CC0-1.0`  |

## Step 3: Deduplicate

After canonicalizing, discard any entry whose canonical form has already been
seen. Common sources of duplicates in cargo output:

- `Apache-2.0 OR MIT` and `MIT OR Apache-2.0` → keep one
- `BSD-3-Clause AND MIT` and `MIT AND BSD-3-Clause` → keep one
- Multiple word-order variants of the same triple (e.g. `Apache-2.0 OR MIT OR
  Zlib`, `MIT OR Zlib OR Apache-2.0`, `Zlib OR Apache-2.0 OR MIT`) → keep one

## Step 4: Classify Each Unique Entry

**Simple OR** — two or more licenses joined by OR; will be wrapped in parens:
- `Apache-2.0 OR MIT` → `(Apache-2.0 OR MIT)`

**Simple AND** — two licenses both required (cargo uses AND when there is no
choice); will be wrapped in parens:
- `BSD-3-Clause AND MIT` → `(BSD-3-Clause AND MIT)`
- `Apache-2.0 AND ISC` → `(Apache-2.0 AND ISC)`

> **Critical:** if cargo says AND, the License field must say AND. Never convert
> AND to OR — they carry different legal obligations.

**Standalone** — a single license identifier; no parens needed:
- `Apache-2.0`, `ISC`, `bzip2-1.0.6`

**Compound AND with OR sub-expression** — entries like
`(Apache-2.0 OR MIT) AND BSD-3-Clause`. Do **not** add these as compound terms;
their component licenses are already covered as separate entries. Discard after
confirming all components are present in the list.

## Step 5: Sort

Sort all entries by their inner expression text (strip outer parens for the sort
key) using strict ASCII byte order:

```
( < 0-9 < A-Z < a-z
```

Practical consequences:
- Entries starting with a digit (`0BSD`) sort before uppercase letters
- Entries starting with a lowercase letter (`bzip2-1.0.6`) sort **after** all
  uppercase entries — `bzip2-1.0.6` comes after `Zlib`, not between `BSL-1.0`
  and `CC0-1.0`
- Among entries sharing the same prefix, the shorter one sorts first:
  `Apache-2.0` → `Apache-2.0 AND ISC` → `Apache-2.0 OR ...`
- AND sorts before OR at the same prefix level (`A` < `O`)

## Step 6: Write the License Field

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

## Step 7: Verify

Compare the new field against the old one and account for every difference:

- **Entry removed** — confirm no matching comment block entry exists (stale from
  a prior version)
- **Entry added** — confirm it maps to a comment block entry
- **AND ↔ OR change** — always a substantive correction; note it explicitly
- **Reordered only** — cosmetic, no action needed
