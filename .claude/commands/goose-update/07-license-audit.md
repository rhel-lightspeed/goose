# Phase 7: License Audit

Verify all licenses are Fedora-approved and update the spec's License field.

All licenses MUST be valid SPDX identifiers listed in the Fedora approved
license list:
- Approved licenses: https://docs.fedoraproject.org/en-US/legal/license-approval/
- Not allowed licenses: https://docs.fedoraproject.org/en-US/legal/not-allowed-licenses/

Requires: Phase 6 completed, extracted and patched source with vendor in place.

---

## 7.1 Check for New/Changed Licenses

Run `cargo license` from the extracted and patched source directory (with the
vendor tarball extracted in place) to get an early view of the license breakdown
before building:

```bash
cargo license --avoid-build-deps --avoid-dev-deps 2>/dev/null | sort | uniq -c | sort -rn
```

Compare the output against the current license list in the spec file comment
block (the block above the `License:` field). Note any new licenses or crates
that changed license.

After building, the `%{cargo_license_summary}` macro outputs the authoritative
license breakdown. Use the `cargo license` results as a preemptive check to
catch issues early, then confirm with `%{cargo_license_summary}` output after
the build.

## 7.2 Problematic License Check

Cross-reference every license found in 7.1 against both lists. Flag any crate
whose license:
- Appears on the **not-allowed** list — the crate MUST be removed or replaced
- Does not appear on the **approved** list — needs Fedora legal review before
  the package can ship
- Is not a valid SPDX identifier — needs correction

**Known licenses requiring special attention in this package:**
- `CC0-1.0` — Listed as "allowed" in Fedora but requires individual legal
  review per crate. The crate `constant_time_eq` was already approved (see
  legal ML thread in spec comments). New CC0-1.0 crates need separate legal
  approval.
- `GPL-2.0` (without `-only` or `-or-later`) — Invalid SPDX, needs correction
  to `GPL-2.0-only` or `GPL-2.0-or-later`
- `AGPL-*` — Check the not-allowed list; may cause distribution concerns
- `SSPL-*` — Not allowed in Fedora
- `BUSL-*` — Not allowed in Fedora
- Any unknown or custom license identifiers

Per Fedora Rust packaging guidelines, the License tag must cover all code
compiled into the final binary, including all vendored crates.

## 7.3 Update License Field

If the license list changed, update the `License:` field in the spec. The field
uses `%{shrink:}` macro and must be a valid SPDX expression. Follow this format:

- Each unique license combination gets its own line
- Use parentheses for OR combinations
- AND between each line (they're all compiled into the binary)
- Keep sorted alphabetically

Also update the comment block above the License field that lists the raw
`%{cargo_license_summary}` output for easy diffing on future updates.

## 7.4 Bundled JS/CSS License Files

If Phase 6.3 found version changes in the minified JavaScript/CSS files:
- Check if upstream merged the license files PR
  (https://github.com/aaif-goose/goose/pull/7352)
  - If merged, the separate Source2-Source7 license files may no longer be needed
  - If not merged, keep them and check if they need updating for the new versions
