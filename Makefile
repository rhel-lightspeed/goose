NAME := goose
PKG_NAME := $(NAME)
TOOL2RPM := rust2rpm
FAS_USERNAME := $(shell copr whoami)

.PHONY: create-copr-repo
create-copr-repo:
	copr create \
		--chroot fedora-rawhide-x86_64 \
		$(NAME)

.PHONY: sources
sources:
	spectool -g $(NAME).spec

.PHONY: srpm
srpm:
	fedpkg --release rawhide srpm

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
	rm -rf *.src.rpm *.tar.gz *.tar.xz *.crate vendor

.PHONY: freeze
freeze:
	./scripts/freeze.py --python-versions 3.14
