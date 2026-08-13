# Phase 1: Source Setup & Pre-flight Checks

Update the spec version, download the new source, and validate that the target
version can be packaged before proceeding.

Requires: `TARGET_VERSION` to be set (passed from the orchestrator or as
`$ARGUMENTS`).

---

## 1.0 Read Past Lessons Learned

Read `docs/lessons-learned.md` in full before doing anything else. It records
past mistakes and workflow gaps found in previous updates — apply that
context throughout the phases below instead of re-discovering the same
issues.

## 1.1 Verify Required Tools

Check that all required tools are available (see AGENTS.md for the full list):

```bash
missing=()
for tool in rg fd cargo cargo2rpm fedpkg gh patch rpmspec sed spectool strings tar; do
  command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done
if [ ${#missing[@]} -ne 0 ]; then
  echo "MISSING TOOLS: ${missing[*]}"
else
  echo "All tools available"
fi
```

If any tools are missing, warn the user and stop. Refer to the tool table in
AGENTS.md for package names.

## 1.2 Update Spec Version

Edit `goose.spec` to update the `Version:` tag to the target version.

**Do NOT** change the `Release:` tag — it uses `%autorelease`.

## 1.3 Download and Extract Source

```bash
spectool -g goose.spec
tar xf goose-{TARGET_VERSION}.tar.gz
```

The extracted source will be reused by subsequent phases — do not delete it.

## 1.4 Version Blocker Analysis

Check if the target version introduces blocking dependencies by searching
the local `Cargo.lock`:

```bash
rg -c '^name = "(v8|v8-sys|deno-core|deno[-_]|swc[-_]?|wasm-bindgen)"' \
  goose-{TARGET_VERSION}/Cargo.lock
```

If any matches are found, **STOP** and warn the user:

> This version introduces blocked dependencies ({list}). Per RSPEED-2434, we
> cannot update past versions that pull in v8/deno-core/swc until upstream
> provides a way to disable those features.

## 1.5 Feature Flags Analysis

Read the workspace and per-crate `Cargo.toml` files from the extracted source
to discover what feature names exist upstream (this is discovery only — do
not edit these files):

```bash
# Workspace features
rg -A 20 '^\[features\]' goose-{TARGET_VERSION}/Cargo.toml

# Per-crate features for main binaries
for toml in goose-{TARGET_VERSION}/crates/*/Cargo.toml; do
  if rg -q '^\[features\]' "$toml"; then
    echo "=== $toml ==="
    rg -A 20 '^\[features\]' "$toml"
  fi
done
```

Compare the discovered feature names against the current
`%{downstream_features}` macro in `goose.spec`:

```bash
rg '%global downstream_features' goose.spec
```

For each **new** feature name that exists upstream but is not yet in
`%{downstream_features}`:

1. Check whether it is required for something we already ship (rare — most
   new features are opt-in additions). If unsure, ask the user whether it
   should be added to `%{downstream_features}`.
2. Do **not** touch `Cargo.toml`. Per AGENTS.md ("Downstream Feature Flags"),
   `--no-default-features` already means any feature not listed in
   `%{downstream_features}` is inactive — there is nothing to disable.

Note: the authoritative `cargo tree --no-default-features --features
"%{downstream_features}" -i <crate>` decision test from AGENTS.md requires
dependency patches applied and the vendor tarball in place — that
environment doesn't exist yet at this point in the update (see Phase
2/3.1). Record any new-feature decisions made here and re-verify them in
Phase 3.1 once that environment is ready; if a forbidden crate turns out to
be reachable there, that's a dependency-patch case for Phase 2/3, not
something to fix in this phase by editing `Cargo.toml`.

**Mandatory feature rules (see AGENTS.md for the full rationale):**
- `native-tls` MUST always be in `%{downstream_features}` — we never use
  rustls
- A feature must NEVER be added to `%{downstream_features}` if the release
  notes or `Cargo.toml` show it depends on `v8`, `deno-core`, or `swc`
- Any other new feature: STOP and ask the user whether to add it to
  `%{downstream_features}` before proceeding — do not decide unilaterally

## 1.6 Upstream Changelog Review

Fetch the release notes (these are not in the tarball):

```bash
gh release view v{TARGET_VERSION} --repo aaif-goose/goose
```

Summarize for the user:
- New features added
- Dependencies added/removed/changed
- Breaking changes
- New binary targets (check `[[bin]]` sections in workspace Cargo.toml)
- New workspace crates (check for new `crates/` directories)

Ask the user to confirm they want to proceed.

## Verification

- [ ] All required tools available
- [ ] Spec `Version:` tag updated
- [ ] Source tarball downloaded and extracted
- [ ] No blocking dependencies found in `Cargo.lock`
- [ ] New upstream feature names compared against `%{downstream_features}`;
  no unilateral additions made
- [ ] `Cargo.toml` was not modified in this phase
- [ ] User confirmed they want to proceed
