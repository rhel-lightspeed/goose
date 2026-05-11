# Phase 10: Build Verification

Final verification and next steps.

Requires: All previous phases completed, spec file fully updated.

---

## 10.1 Local SRPM Build

```bash
fedpkg srpm
```

Verify the SRPM builds without errors. This is a basic sanity check — it
validates that the spec parses correctly, all Source/Patch files exist, and
`%prep` completes. The full build verification happens via Packit/COPR in the
next step.

## 10.2 Changelog

The spec uses `%autochangelog` — do NOT manually edit the changelog. The
changelog is auto-generated from git commit messages by `rpmautospec` at build
time. Ensure the commit message for this update is descriptive (e.g.,
"Update to version {TARGET_VERSION}").

## 10.3 Suggest Next Steps

After all phases complete, tell the user:

1. **Review the changes** with `git diff`
2. **Create a PR branch** and commit
3. **Push to trigger Packit** — Packit will run COPR builds on PR creation
   targeting all architectures and distribution versions listed in
   `.packit.yaml`
4. **After COPR passes**, the package is ready for fedpkg submission
