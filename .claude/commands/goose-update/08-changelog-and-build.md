# Phase 8: Changelog & Build Verification

Write the changelog entry, then build and verify the SRPM.

Requires: All previous phases completed, spec file fully updated.

---

## 8.1 Fetch Upstream Release Notes

```bash
gh release view v{TARGET_VERSION} --repo aaif-goose/goose
```

## 8.2 Filter Excluded Items

Go through every entry in the upstream release notes and remove anything that
falls into the categories below. **When an entry is ambiguous, check the
linked PR** (use `gh pr view` or similar) to inspect which files were changed
— if the PR only touches excluded code, drop the entry.

### Disabled features (never shipped downstream)

Remove any entry whose linked PR touches code gated behind these features:

- `code-mode` — v8/deno/swc JavaScript engine
- `local-inference` — llama-cpp/candle local ML inference
- `aws-providers` — AWS SDK integration
- `nostr` — Nostr protocol (encrypted Nostr session sharing, etc.)

### UI / Desktop / Electron

Remove **all** UI-related entries. The `ui/` folder is stripped in `%prep` and
we do not ship a desktop application. This includes but is not limited to:

- Desktop/Electron window management, sidebar, fullscreen, tray, etc.
- Desktop chat, onboarding, settings screens, provider selection UI
- Inline code snippet styling, chat composer, context panel
- Any entry that only affects the desktop or web frontend

### Excluded platforms

- Windows-specific fixes (winapi, winreg, Windows Console Host, etc.)
- macOS-specific fixes (metal, apple-native keyring, macOS fullscreen, etc.)

### Documentation

- Documentation-only entries — docs are not shipped in the RPM

### Judgment calls

- If an entry mentions "desktop" or "UI" but the linked PR also changes
  CLI/server code, **keep it** and reword to cover only the CLI/server part
- Provider-related entries should be kept even if they mention "desktop" in
  passing — they affect the CLI/server too
- If an entry spans both excluded and included functionality, reword to cover
  only the included part

## 8.3 Write the Changelog Entry

Prepend a new entry to the top of the `changelog` file:

```
* {Day} {Mon} {DD} {YYYY} {Packager Name} <{email}> - {TARGET_VERSION}-1
- Update to version {TARGET_VERSION}
- {entry 1}
- {entry 2}
...
```

### RPM changelog format rules

- **Header line**: `* %a %b %d %Y Full Name <email> - Version-Release`
- **Date**: use the date of the upstream release, not today's date
- **Packager**: get from `git config user.name` / `git config user.email`
- **Flat list**: every entry is a top-level `- ` bullet — no sub-bullets, no
  grouping headers (no "Features:", "Bug Fixes:", etc.)
- **One line per entry**: no line wrapping within a bullet
- **Concise**: keep entries short but descriptive
- **First entry** is always `- Update to version {TARGET_VERSION}`

## 8.4 Local SRPM Build

```bash
fedpkg --release rawhide srpm
```

Verify the SRPM builds without errors. This validates that the spec parses
correctly, all Source/Patch files exist, and `%prep` completes.

## 8.5 Retro & Lessons Learned

Before wrapping up, review this session against the phase files:

1. Did any phase's instructions turn out to be wrong, ambiguous, or
   incomplete — i.e. did you have to guess, improvise, or ask the user
   something the phase file should have told you deterministically?
2. Did you hit a new case not covered by AGENTS.md or any phase file (a new
   kind of `-sys` crate, a new patch conflict pattern, a new forbidden
   dependency path, etc.)?

If the answer to either is yes:

- Draft a new entry for `docs/lessons-learned.md` using the template at the
  top of that file. Prepend it (newest entries first).
- Propose concrete edits to the specific phase file(s) or AGENTS.md section
  that should change so the same issue doesn't require a judgment call next
  time.
- Show both the lessons-learned entry and the proposed phase-file diffs to
  the user and ask for confirmation before writing them.

If nothing new was learned this run (the phases worked as documented), say so
explicitly and skip this step — do not manufacture a lessons-learned entry
just to have one.

## 8.6 Suggest Next Steps

After all phases complete, tell the user:

1. **Review the changes** with `git diff`
2. **Create a PR branch** and commit
3. **Push to trigger Packit** — Packit will run COPR builds on PR creation
   targeting all architectures and distribution versions listed in
   `.packit.yaml`
4. **After COPR passes**, the package is ready for fedpkg submission

## Verification

- [ ] Changelog has the new entry at the top with correct format
- [ ] All previous entries preserved below
- [ ] No entries for disabled features, UI/desktop, or excluded platforms
- [ ] SRPM builds without errors
- [ ] Session reviewed for lessons learned; new entry added (or explicitly
  confirmed nothing new was learned)
