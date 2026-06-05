NAME := goose
PKG_NAME := $(NAME)
TOOL2RPM := rust2rpm
FAS_USERNAME := $(shell copr whoami)
DIST_GIT_CHECKOUT ?= ../goose-fedora
VERSION := $(shell rpmspec -q --qf "%{VERSION}" goose.spec)
VENDOR_TARBALL := goose-$(VERSION)-vendor.tar.xz
SRPM = $(shell srpm=$$(ls goose-$(VERSION)*.src.rpm 2>/dev/null | tail -n 1); if [ -f "$$srpm" ]; then echo $$(realpath "$$srpm"); else echo MISSING; fi)

.PHONY: create-copr-repo
create-copr-repo:
	copr create \
		--chroot fedora-rawhide-x86_64 \
		$(NAME)

.PHONY: sources
sources:
	spectool -g $(NAME).spec

# Dynamic targets that will not run if the file exists.
$(VENDOR_TARBALL):
	./generate-vendor-tarball.sh

$(SRPM):
	fedpkg --release rawhide srpm

# Static targets that provide a consistent interface.
.PHONY: vendor-tarball
vendor-tarball: $(VENDOR_TARBALL)

.PHONY: srpm
srpm: vendor-tarball $(SRPM)

.PHONY: import
import: srpm
	@(cd $(DIST_GIT_CHECKOUT) && fedpkg import $(SRPM))

.PHONY: build
build: srpm
	copr build $(NAME) $(NAME)*.src.rpm \
		--chroot fedora-rawhide-x86_64 \
		--timeout 36000

.PHONY: build-all
build-all: srpm
	copr build $(NAME) $(NAME)*.src.rpm \
		--chroot fedora-43-x86_64 \
		--chroot fedora-43-aarch64 \
		--chroot fedora-43-ppc64le \
		--chroot fedora-43-s390x \
		--chroot fedora-44-x86_64 \
		--chroot fedora-44-aarch64 \
		--chroot fedora-44-ppc64le \
		--chroot fedora-44-s390x \
		--chroot fedora-rawhide-x86_64 \
		--chroot fedora-rawhide-aarch64 \
		--chroot fedora-rawhide-ppc64le \
		--chroot fedora-rawhide-s390x \
		--chroot epel-9-x86_64 \
		--chroot epel-9-aarch64 \
		--chroot epel-9-ppc64le \
		--chroot epel-9-s390x \
		--chroot epel-10-x86_64 \
		--chroot epel-10-aarch64 \
		--chroot epel-10-ppc64le \
		--chroot epel-10-s390x \
		--chroot rhel-9-x86_64 \
		--chroot rhel-9-aarch64 \
		--chroot rhel-9-ppc64le \
		--chroot rhel-9-s390x \
		--chroot rhel-10-x86_64 \
		--chroot rhel-10-aarch64 \
		--chroot rhel-10-ppc64le \
		--chroot rhel-10-s390x \
		--timeout 36000

.PHONY: logs
logs:
	@command -v fuzzytail > /dev/null || { echo >&2 "fuzzytail is not installed. Install with pip install fuzzytail"; }
	fuzzytail watch $(FAS_USERNAME)/$(NAME)

.PHONY: clean
clean:
	rm -rf *.src.rpm *.tar.gz *.tar.xz *.crate vendor goose-*

.PHONY: freeze
freeze:
	./scripts/freeze.py --python-versions 3.14
