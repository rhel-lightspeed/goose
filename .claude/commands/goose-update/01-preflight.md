# Phase 1: Pre-flight Checks

This phase validates that the target version can be packaged before any work
begins. Run this before making any changes to the spec or source.

Requires: `TARGET_VERSION` to be set (passed from the orchestrator or as
`$ARGUMENTS`).

---

## 1.1 Version Blocker Analysis

Before proceeding with ANY version update, check if the target version
introduces any of these **blocking dependencies**:

- `v8` or `v8-sys` — V8 JavaScript engine, extremely difficult to package
- `deno-core` or `deno_*` — Deno runtime components
- `swc` or `swc_*` — SWC compiler, complex native build
- `wasm-bindgen` — WebAssembly bindings (if pulled in as a build dep)

To check, download the upstream `Cargo.lock` for the target version and search
it locally (the file is too large for WebFetch):

```bash
curl -sL https://raw.githubusercontent.com/aaif-goose/goose/v{TARGET_VERSION}/Cargo.lock -o /tmp/goose-upstream-Cargo.lock
rg -c '^name = "(v8|v8-sys|deno-core|deno[-_]|swc[-_]?|wasm-bindgen)"' /tmp/goose-upstream-Cargo.lock
```

If any matches are found, **STOP** and warn the user:

> This version introduces blocked dependencies ({list}). Per RSPEED-2434, we
> cannot update past versions that pull in v8/deno-core/swc until upstream
> provides a way to disable those features. The current constraint is documented
> in the spec file header comment.

## 1.2 Feature Flags Analysis

Goose upstream uses Cargo feature flags. Fetch the workspace `Cargo.toml` and
check for feature definitions:

```
WebFetch https://raw.githubusercontent.com/aaif-goose/goose/v{TARGET_VERSION}/Cargo.toml
```

Also check per-crate `Cargo.toml` files for the main crates (`goose-cli`,
`goosed`, `goose-server`, etc.).

**Mandatory feature rules:**
- `native-tls` MUST always be enabled — we never use rustls
- Any feature that pulls in `v8`, `deno-core`, or `swc` MUST be disabled
- Other features should be evaluated case-by-case with the user

Report to the user:
- What features exist and what they do
- Which features are safe to enable
- Which features would pull in blocked dependencies
- Recommend which features to enable/disable

## 1.3 Upstream Changelog Review

Fetch the release notes for all versions between current and target:

```
WebFetch https://github.com/aaif-goose/goose/releases/tag/v{TARGET_VERSION}
```

Summarize for the user:
- New features added
- Dependencies added/removed/changed
- Any breaking changes
- Any new binary targets (check `[[bin]]` sections in workspace Cargo.toml)
- Any new crates added to the workspace (check for new `crates/` directories)

Ask the user to confirm they want to proceed after reviewing the summary.
