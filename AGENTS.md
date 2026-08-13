# AGENTS.md

## Project Overview

This is a Fedora/RHEL RPM packaging repository for
[goose](https://github.com/block/goose), an AI agent framework written in Rust.
The package uses vendored dependencies, downstream patches, and must comply with
Fedora packaging guidelines and a Fedora package review (BZ#2428704).

## Repository Structure

```
goose.spec                 # RPM spec file
generate-vendor-tarball.sh # Script to produce the vendored crate tarball
0000-0099 patches          # Dependency patches (Cargo.toml modifications)
0100-0799 patches          # Vendor/source patches
0800-0899 patches          # RHEL-only patches (applied conditionally)
*.license                  # License files for bundled JS/CSS libraries
.claude/commands/          # Agent commands for version updates
docs/                      # Human-readable documentation
docs/lessons-learned.md    # Log of past update surprises/fixes; read before
                            # starting an update, append to after one
```

## Required Tools

These tools must be available before running any update command. If any are
missing, warn the user and stop.

```bash
for tool in rg fd cargo cargo2rpm fedpkg gh patch rpmspec sed spectool strings tar; do
  command -v "$tool" >/dev/null 2>&1 && echo "OK: $tool" || echo "MISSING: $tool"
done
```

| Tool | Package / Install | Used For |
|------|-------------------|----------|
| `rg` | `ripgrep` | Content search across source/spec/vendor |
| `fd` | `fd-find` | File discovery in source/vendor trees |
| `cargo` | `cargo` | Dependency tree inspection (`cargo tree`) |
| `cargo2rpm` | `cargo2rpm` | License summary (same as `%{cargo_license_summary}`) |
| `fedpkg` | `fedpkg` | SRPM builds |
| `gh` | `gh` | Upstream release notes |
| `patch` | `patch` | Patch testing (`--dry-run`) and application |
| `rpmspec` | `rpm-build` | Spec file queries |
| `sed` | `sed` | Spec/config editing |
| `spectool` | `rpmdevtools` | Source tarball downloads |
| `strings` | `binutils` | Extracting bundled asset lists |
| `tar` | `tar` | Tarball extraction |

## Philosophy

Agent commands in this repository follow these principles:

1. **Discovery over declaration** — Commands describe *what to verify* and
   *how to verify it*, not hardcoded lists of patch names, crate names, or
   workaround details. The agent discovers the current state by reading files
   and running tools.

2. **Local over remote** — Work from the tarball downloaded via `spectool -g`.
   Never fetch individual files from GitHub. Use `gh release view` only for
   release notes (not in the tarball).

3. **Verify deterministically** — Use `patch -p1 --dry-run`, `fd`, `rg`,
   `diff` to confirm things work. Don't rely on prose descriptions of what
   "should" be there.

4. **`.orig` pattern for modifications** — Before modifying any file in the
   extracted source, copy it to `.orig`. Generate patches with
   `diff -u --label`:

   ```bash
   cp path/to/Cargo.toml path/to/Cargo.toml.orig
   # ... make changes ...
   diff -u \
     --label a/path/to/Cargo.toml \
     --label b/path/to/Cargo.toml \
     path/to/Cargo.toml.orig path/to/Cargo.toml
   ```

5. **Each phase owns its verification** — Every phase ends by verifying its
   own work with deterministic checks. Don't defer verification to a later
   phase.

## Patch Numbering Convention

Patches are organized by number range and purpose:

| Range | Category | In vendor script? | Applied when |
|-------|----------|-------------------|--------------|
| `0000-0099` | Dependency patches (Cargo.toml) | Yes — listed in `PATCHES` array | Always |
| `0100-0799` | Vendor-targeting and source patches | No | Always (`%autopatch -M 799`) |
| `0800-0899` | RHEL-only patches | No | `%if 0%{?rhel}` in `%prep` |

Dependency patches (0000-0099) affect `Cargo.toml`/`Cargo.lock` and therefore
what gets vendored. They must be listed in `generate-vendor-tarball.sh`'s
`PATCHES` array.

## Downstream Feature Flags

Feature selection is expressed as explicit cargo arguments — **never** as
patched `Cargo.toml` defaults. The canonical feature set is stored in the
spec's `%{downstream_features}` macro and must be identical across three
call sites:

1. `%cargo_build -n -f "%{downstream_features}"` in `%build`
2. `%cargo_test -n -f "%{downstream_features}"` in `%check`
3. `cargo vendor-filterer --no-default-features --features ...` in
   `generate-vendor-tarball.sh`

The `-n` flag (`--no-default-features`) is mandatory because upstream defaults
include `rustls-tls` and `aws-providers`, which pull in forbidden content.

### Do not patch Cargo.toml just to "turn off" a feature

`--no-default-features` already deactivates every feature that is not
explicitly listed in `%{downstream_features}`. A feature that is simply
absent from that list is already disabled — there is nothing further to do,
and no patch should be created or modified to remove it, comment it out, or
rewrite its `default = [...]` list.

**Decision test before touching any Cargo.toml over a feature/dependency
concern:** from the extracted source with dependency patches applied and
vendor in place, run:

```bash
cargo tree --no-default-features --features "%{downstream_features}" -i <crate>
```

- **Exit non-zero (not found)** — The existing build-time flags already
  exclude it. Do nothing. Do not add or edit a patch.
- **Exit zero (found)** — The dependency is reachable *even with* our feature
  flags applied, meaning some crate pulls it in unconditionally (e.g. via a
  required dependency, or via another crate's own `default` features that our
  top-level flags don't control). Only in this case is a dependency patch
  (0000-0099) justified, and only to address that specific unconditional
  path — not to restate the feature selection already expressed by
  `%{downstream_features}`.

  Example: `0004-aws-lc-rs-feature-flag.patch` exists because `rcgen` enables
  `aws-lc-rs` as one of its own defaults regardless of goose's top-level
  features, so `-n -f "%{downstream_features}"` alone can't stop it.

If you find yourself about to regenerate a Cargo.toml patch whose only effect
is removing a feature from a `default = [...]` list, stop — that is very
likely redundant with `--no-default-features` and should not be done.

## Forbidden Dependencies

These crates must not appear in the dependency tree or vendor tarball:

| Crate | Reason |
|-------|--------|
| `rustls` | All TLS must go through `native-tls` (OpenSSL) |
| `aws-lc-rs` / `aws-lc-sys` | Forbidden entirely — not just prebuilt binaries |
| `v8` / `v8-sys` / `deno-core` / `swc` | Extremely difficult to package, blocked per RSPEED-2434 |

Verify with `cargo tree --no-default-features --features <downstream_features> -i <crate>`.

## Source and Patch Declaration Rules

- `Source` and `Patch` tags MUST be declared unconditionally — never inside
  `%if`/`%endif` blocks
- Conditionals are applied in `%prep` using `%autopatch` with `-m`/`-M` ranges
- Each `Patch` tag must include a comment explaining its purpose
- The SRPM must always contain all files regardless of build target

## Fedora Compliance References

- [Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/)
- [Fedora Rust Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/Rust/)
- [Approved Licenses](https://docs.fedoraproject.org/en-US/legal/license-approval/)
- [Not Allowed Licenses](https://docs.fedoraproject.org/en-US/legal/not-allowed-licenses/)
- Package review: BZ#2428704

## Key Constraints

- **No pushing**: Never push to any remote. Branches and commits are fine.
- **Fedora compliance**: All changes must follow the guidelines linked above.
- **Patch declarations**: Always unconditional (see rules above).
