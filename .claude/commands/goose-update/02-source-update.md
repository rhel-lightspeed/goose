# Phase 2: Source Update

Update the spec file version and download the new source tarball.

Requires: Phase 1 completed, `TARGET_VERSION` confirmed with user.

---

## 2.1 Update Spec Version

Edit `goose.spec` to update the `Version:` tag to the target version.

**Do NOT** change the `Release:` tag — it uses `%autorelease`.

## 2.2 Download New Source Tarball

```bash
spectool -g goose.spec
```
