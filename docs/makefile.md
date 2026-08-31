# Makefile Reference

This document describes the Makefile targets available for building and
managing the goose RPM package.

## Prerequisites

The following tools must be available in your environment, either installed
locally or inside a development container:

- `fedpkg`
- `spectool`
- `copr-cli`
- `fuzzytail` (optional, for `make logs`)

## Targets

### `create-copr-repo`

Creates a new [COPR](https://copr.fedorainfracloud.org) repository for
building goose. This is a one-time setup step and only needs to be run when
bootstrapping the project from scratch.

The repository is created with the following chroots enabled:

- `fedora-rawhide-x86_64`

```bash
make create-copr-repo
```

### `sources`

Downloads the source tarballs defined in `goose.spec` using `spectool`. The
files are placed in the repository root directory.

```bash
make sources
```

### `vendor-tarball`

Generates the vendored crate tarball using `generate-vendor-tarball.sh`. This
is a prerequisite of the `srpm` target and is skipped if the tarball already
exists.

```bash
make vendor-tarball
```

### `srpm`

Generates a source RPM (`.src.rpm`) using `fedpkg` targeting the Rawhide
release. Depends on `vendor-tarball` to ensure the vendored crate tarball
exists first. This is automatically called by the `build` target, but can be
run independently to verify that the spec file produces a valid SRPM.

```bash
make srpm
```

### `import`

Imports the SRPM into the dist-git checkout directory. Depends on `srpm` to
ensure the SRPM exists. Runs `fedpkg import` inside the directory specified
by the `DIST_GIT_CHECKOUT` variable (defaults to `../goose-fedora`).

```bash
make import

# Or with a custom dist-git checkout path
make import DIST_GIT_CHECKOUT=/path/to/dist-git
```

### `build`

Builds the package in COPR. This target first generates an SRPM (via the
`srpm` dependency), then submits it to the COPR build system targeting
`fedora-rawhide-x86_64` with a 10-hour timeout.

```bash
make build
```

### `build-all`

Builds the package in COPR across all supported chroots: Fedora 43, 44, and
Rawhide (x86_64, aarch64, ppc64le, s390x), EPEL 9 and 10, and RHEL 9 and 10.
Uses a 10-hour timeout.

```bash
make build-all
```

### `logs`

Watches COPR build logs in real time using
[fuzzytail](https://pypi.org/project/fuzzytail/). Requires `fuzzytail` to be
installed (`pip install fuzzytail`). The command will display an error message
if the tool is not found.

```bash
make logs
```

### `clean`

Removes generated build artifacts from the repository root:

- `*.src.rpm` -- source RPMs
- `*.tar.gz`, `*.tar.zstd` -- source tarballs
- `*.crate` -- Rust crate archives
- `vendor/` -- vendored dependencies directory
- `goose-*` -- extracted source and vendor directories

```bash
make clean
```

### `freeze`

Freezes Python dependency versions for the goose Python extensions. Runs
`scripts/freeze.py` targeting Python 3.14 to produce pinned requirement files
under `requirements/`.

```bash
make freeze
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DIST_GIT_CHECKOUT` | `../goose-fedora` | Path to the dist-git checkout used by `make import`. Override with `make import DIST_GIT_CHECKOUT=/path/to/checkout`. |
| `SRPM` | Auto-detected | Resolves to the absolute path of the most recent `.src.rpm` in the repo root, or `MISSING` if none exists. |
| `VERSION` | From spec | Extracted from `goose.spec` using `rpmspec`. |
| `VENDOR_TARBALL` | `goose-$(VERSION)-vendor.tar.zstd` | Name of the vendored crate tarball. |

## Typical Workflow

A standard build cycle looks like this:

```bash
# 1. Download the sources defined in the spec file
make sources

# 2. Build the SRPM and submit to COPR
make build

# 3. (Optional) Watch the build logs
make logs

# 4. Clean up artifacts when done
make clean
```

## Related Documentation

- [Version Update Process](update-process.md) -- how to update goose to a new
  upstream version using the Claude Code automation
