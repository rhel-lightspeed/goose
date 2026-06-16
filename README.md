[![Copr build status](https://copr.fedorainfracloud.org/coprs/g/rhel-lightspeed/goose/package/goose/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/rhel-lightspeed/goose/package/goose/)

# Goose

This is the development repository for the Fedora/RHEL RPM packaging of
[goose](https://github.com/block/goose). It is the upstream source for the
dist-git version of the package. Changes are developed and tested here before
being submitted to dist-git.

* [COPR repo](https://copr.fedorainfracloud.org/coprs/g/rhel-lightspeed/goose)
* [Upstream repo](https://github.com/aaif-goose/goose)
* [Upstream license](https://github.com/aaif-goose/goose/blob/main/LICENSE)
* [Fedora Package Review Bugzilla](https://bugzilla.redhat.com/show_bug.cgi?id=2428704)

## Documentation

- [Makefile Reference](docs/makefile.md) -- build targets and typical workflow
- [Version Update Process](docs/update-process.md) -- how to update to a new
  upstream version

## Setup

Before executing a new build, run the initial setup first:

```bash
# Create a new copr repository
make create-copr-repo
```

## Building

To build this RPM via copr, the following commands are required:

```bash
# Will pull the sources from goose.spec and place in the root directory
make sources

# Will perform two operations:
#   * Generate a new srpm with `fedpkg --release rawhide srpm`
#   * Request a new build on copr
make build
```
