# Phase 10: Build Verification

Final verification and next steps.

Requires: All previous phases completed, spec file fully updated.

---

## 10.1 Local SRPM Build

```bash
fedpkg --release rawhide srpm
```

Verify the SRPM builds without errors. This is a basic sanity check — it
validates that the spec parses correctly, all Source/Patch files exist, and
`%prep` completes. The full build verification happens via Packit/COPR in the
next step.

## 10.2 Changelog

The changelog is maintained in a separate `changelog` file with upstream release
notes. Run Phase 11 (`goose-update/11-changelog-update.md`) to update it with
the new version's upstream changelog.

## 10.3 Suggest Next Steps

After all phases complete, tell the user:

1. **Review the changes** with `git diff`
2. **Create a PR branch** and commit
3. **Push to trigger Packit** — Packit will run COPR builds on PR creation
   targeting all architectures and distribution versions listed in
   `.packit.yaml`
4. **After COPR passes**, the package is ready for fedpkg submission
