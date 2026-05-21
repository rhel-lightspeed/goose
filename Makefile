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
