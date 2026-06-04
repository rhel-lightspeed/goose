# Phase 11: Changelog Update

Update the `changelog` file with the upstream goose release notes for the new
version. The first release (`-1`) of each upstream version uses the upstream
changelog; downstream-only modifications are appended as subsequent releases
(`-2`, `-3`, etc.).

Requires: Phase 1 completed (upstream changelog reviewed), `TARGET_VERSION`
confirmed with user.

---

## 11.1 Fetch Upstream Release Notes

Fetch the release notes for the target version:

```
WebFetch https://github.com/aaif-goose/goose/releases/tag/v{TARGET_VERSION}
```

## 11.2 Filter Excluded Items

Go through every entry in the upstream release notes and remove anything that
falls into the categories below. **When an entry is ambiguous, check the
linked PR** (use `gh pr view` or `mcp__github__pull_request_read`) to inspect
which files were changed — if the PR only touches excluded code, drop the
entry.

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

- Windows-specific fixes (winapi, winreg, Windows Console Host, `az.cmd`,
  WSL2 detection, Windows CUDA artifacts, etc.)
- macOS-specific fixes (metal, apple-native keyring, macOS fullscreen, etc.)

### Documentation

- Documentation-only entries — docs are not shipped in the RPM

### Judgment calls

- If an entry mentions "desktop" or "UI" but the linked PR also changes
  CLI/server code, **keep it** and reword to cover only the CLI/server part
- Provider-related entries (Ollama, OpenAI, Anthropic, etc.) should be kept
  even if they mention "desktop" in passing — they affect the CLI/server too
- If an entry spans both excluded and included functionality, reword to cover
  only the included part

## 11.3 Write the Changelog Entry

Prepend a new entry to the top of the `changelog` file following standard RPM
changelog conventions:

```
* {Day} {Mon} {DD} {YYYY} {Packager Name} <{email}> - {TARGET_VERSION}-1
- Update to version {TARGET_VERSION}
- {entry 1}
- {entry 2}
- {entry 3}
...
```

### RPM changelog format rules

- **Header line**: `* %a %b %d %Y Full Name <email> - Version-Release`
- **Date**: use the date of the upstream release, not today's date
- **Packager**: get from `git config user.name` / `git config user.email`
- **Flat list**: every entry is a top-level `- ` bullet — no sub-bullets, no
  grouping headers (no "Features:", "Bug Fixes:", etc.)
- **One line per entry**: no line wrapping within a bullet
- **Concise**: keep entries short but descriptive enough to be useful
- **First entry** is always `- Update to version {TARGET_VERSION}`

## 11.4 Verify

Check that the changelog file:
1. Has the new entry at the top
2. Preserves all previous entries below
3. Uses correct RPM changelog date format (`%a %b %d %Y`)
4. Has the correct `Version-Release` (`{TARGET_VERSION}-1`)
5. Uses a flat list with no sub-bullets or grouping headers
6. Contains no entries for disabled features, UI/desktop, or excluded platforms

Show the user the new entry for review before proceeding.
