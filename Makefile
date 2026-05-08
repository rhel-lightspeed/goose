NAME := goose
PKG_NAME := $(NAME)
TOOL2RPM := rust2rpm
FAS_USERNAME := r0x0d
FILES_TO_SYNC := $(wildcard *.src.rpm) $(wildcard *.spec) generate-vendor-tarball.sh

ifneq ("$(wildcard rust2rpm.toml)","")
FILES_TO_SYNC += rust2rpm.toml
endif

.PHONY: create-copr-repo
create-copr-repo:
	copr create \
		--chroot fedora-43-x86_64 \
		--chroot fedora-44-x86_64 \
		--chroot fedora-rawhide-x86_64 \
		$(NAME)

.PHONY: create-gh-repo
create-gh-repo:
	git init
	git add . && git commit -m "Initial commit for $(NAME)"
	gh repo create $(NAME) \
		--public \
		--disable-wiki \
		--remote origin \
		--source . \
		--push \
		--description "Upstream rpm repository for https://github.com/block/goose"

.PHONY: spec
spec:
	@echo "Goose is not packaged in crates.io. Skipping."

.PHONY: sources
sources:
	spectool -g $(NAME).spec

.PHONY: srpm
srpm:
	fedpkg srpm

.PHONY: build
build: srpm
	copr build $(NAME) $(NAME)*.src.rpm \
		--chroot fedora-43-x86_64 \
		--chroot fedora-44-x86_64 \
		--chroot fedora-rawhide-x86_64 \
		--chroot epel-9-x86_64 \
		--chroot epel-10-x86_64 \
		--timeout 36000

.PHONY: logs
logs:
	@command -v fuzzytail > /dev/null || { echo >&2 "fuzzytail is not installed. Install with pip install fuzzytail"; }
	fuzzytail watch $(FAS_USERNAME)/$(NAME)

.PHONY: sync
sync:
	scp $(FILES_TO_SYNC) $(FAS_USERNAME)@fedorapeople.org:/home/fedora/$(FAS_USERNAME)/public_html/$(NAME)

.PHONY: freeze
freeze:
	./scripts/freeze.py --python-versions 3.14
