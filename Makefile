# Makefile for packaging Goose from upstream

NAME := goose
UPSTREAM_REPOSITORY := https://github.com/block/goose/archive/refs/tags/v
TARGET_DIR := target

# Reproducible tar options
TAR_REPRODUCIBLE_OPTS := --sort=name --owner=0 --group=0 --numeric-owner \
	--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime

TAG ?= 1.13.1

RUST_VERSION ?= 1.88.0

# Derived variables
GOOSE_FOLDER := $(NAME)-$(TAG)
GOOSE_TARBALL := $(GOOSE_FOLDER).tar.gz
GOOSE_DIR := $(TARGET_DIR)/$(GOOSE_FOLDER)
PATCHED_TARBALL := $(TARGET_DIR)/$(GOOSE_FOLDER)-patched.tar.zstd
VENDORED_TARBALL := $(TARGET_DIR)/$(GOOSE_FOLDER)-vendor.tar.zstd
VENDOR_CARGO_TOML := $(GOOSE_DIR)/Cargo.toml
FULL_URL := $(UPSTREAM_REPOSITORY)$(TAG).tar.gz

# Get source date epoch from extracted git repo
SOURCE_DATE_EPOCH = $(shell cd $(GOOSE_DIR) && git log -1 --pretty=%ct 2>/dev/null || date +%s)

.PHONY: debug spec clean help download check-deps

help:
	@echo "Goose Fedora Packaging Makefile"
	@echo "================================"
	@echo ""
	@echo "Development workflow:"
	@echo "  make download TAG=X.Y.Z     - Download upstream tarball only"
	@echo "  make check-deps TAG=X.Y.Z   - Check dependencies and update spec file (commit this)"
	@echo ""
	@echo "Build pipeline workflow:"
	@echo "  make spec TAG=X.Y.Z         - Generate optimized tarballs for building"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean                  - Clean all generated files"
	@echo "  make debug                  - Show variables and check dependencies"
	@echo ""
	@echo "Variables:"
	@echo "  TAG=$(TAG)           - Goose version to package"
	@echo "  RUST_VERSION=$(RUST_VERSION)  - Rust toolchain version"
	@echo ""
	@echo "Requirements:"
	@echo "  - cargo-vendor-filterer     - Install with: cargo install cargo-vendor-filterer"
	@echo "  - dnf, python3, tar         - System tools"
	@echo ""
	@echo "Typical usage:"
	@echo "  1. Developer: make check-deps TAG=1.13.1"
	@echo "  2. Review and commit packaging/goose.spec"
	@echo "  3. CI/CD: make spec TAG=1.13.1"

# Download only the upstream tarball
download: $(TARGET_DIR)/$(GOOSE_TARBALL)
	@echo "✅ Downloaded $(GOOSE_TARBALL) to $(TARGET_DIR)/"

# Check dependencies and update spec file (for development/commits)
check-deps: $(GOOSE_DIR)/.extracted
	@echo "🔍 Checking dependencies against Fedora repositories..."
	@echo "   (This may take a few minutes on first run, results are cached)"
	@echo ""
	@./check_fedora_deps.py --all-crates --source-dir $(GOOSE_DIR) --update-spec packaging/$(NAME).spec

# Download upstream goose
$(TARGET_DIR)/$(GOOSE_TARBALL):
	@echo "🚀 Packaging Goose v$(TAG) with Rust $(RUST_VERSION)"
	@mkdir -p $(TARGET_DIR)
	@echo "📥 Downloading goose from $(FULL_URL)"
	curl -L "$(FULL_URL)" -o $@

# Extract tarball
$(GOOSE_DIR)/.extracted: $(TARGET_DIR)/$(GOOSE_TARBALL)
	@echo "📦 Extracting tarball"
	@tar xf $< -C $(TARGET_DIR)
	@touch $@


# Patch Cargo.toml
$(GOOSE_DIR)/.cargo-patched: $(GOOSE_DIR)/.extracted
	@echo "📝 Adding vendor-filter metadata to $(GOOSE_DIR)/Cargo.toml"
	@echo "" >> $(GOOSE_DIR)/Cargo.toml
	@echo "[workspace.metadata.vendor-filter]" >> $(GOOSE_DIR)/Cargo.toml
	@echo 'platforms = ["*-unknown-linux-gnu"]' >> $(GOOSE_DIR)/Cargo.toml
	@echo 'tier = "2"' >> $(GOOSE_DIR)/Cargo.toml
	@echo 'all-features = true' >> $(GOOSE_DIR)/Cargo.toml
	@touch $@

# Patch rust-toolchain.toml
$(GOOSE_DIR)/.rust-toolchain-patched:
	@echo "🔧 Updating rust-toolchain.toml to version $(RUST_VERSION)"
	@if [ -f $(GOOSE_DIR)/rust-toolchain.toml ]; then \
		sed -i 's/channel = "[^"]*"/channel = "$(RUST_VERSION)"/' $(GOOSE_DIR)/rust-toolchain.toml; \
	fi
	@touch $@

# Create vendor-config.toml
$(GOOSE_DIR)/.vendor-config-patched:
	@mkdir -p $(GOOSE_DIR)/.cargo
	@echo '[source."git+https://github.com/nmathewson/crunchy?branch=cross-compilation-fix"]' >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo 'git = "https://github.com/nmathewson/crunchy"' >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo 'branch = "cross-compilation-fix"' >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo 'replace-with = "offline-sources"' >> $(GOOSE_DIR)/.cargo/vendor-config.toml

	@echo "" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo "[source.crates-io]" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo 'replace-with = "offline-sources"' >> $(GOOSE_DIR)/.cargo/vendor-config.toml

	@echo "" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo "[source.offline-sources]" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo 'directory = "/usr/share/cargo/registry"' >> $(GOOSE_DIR)/.cargo/vendor-config.toml

	@echo "" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	@echo "[patch.crates-io]" >> $(GOOSE_DIR)/.cargo/vendor-config.toml
	for dir in vendor/*/; do
		echo "$$(basename "$$dir") = { path = \"vendor/$$(basename "$$dir")\" }"; \
	done >> $(GOOSE_DIR)/.cargo/vendor-config.toml

# Vendor dependencies - creates both tarball and config
$(VENDORED_TARBALL): $(GOOSE_DIR)/.rust-toolchain-patched $(GOOSE_DIR)/.vendor-config-patched
	@echo "📦 Vendoring dependencies with cargo-vendor-filterer"
	@mkdir -p $(GOOSE_DIR)/.cargo
	@cd $(GOOSE_DIR) && \
		cargo vendor-filterer --prefix=vendor --format=tar.zstd ../$(GOOSE_FOLDER)-vendor.tar.zstd
	@if [ ! -f $(TARGET_DIR)/$(GOOSE_FOLDER)-vendor.tar.zstd ]; then \
		echo "❌ Error: Vendor tarball was not created"; \
		exit 1; \
	fi
	@echo "   ✅ Full vendor tarball created: $$(du -h $(TARGET_DIR)/$(GOOSE_FOLDER)-vendor.tar.zstd | cut -f1)"
	@./hack/remove-fedora-packages.sh \
		$(TARGET_DIR)/$(GOOSE_FOLDER)-vendor.tar.zstd \
		$@ \
		packaging/$(NAME).spec \
		$(TARGET_DIR)/vendor-tmp

# Create patched tarball with reproducible options
$(PATCHED_TARBALL): $(VENDORED_TARBALL)
	@echo "📦 Creating patched goose tarball"
	@tar --zstd -cvf $@ $(TAR_REPRODUCIBLE_OPTS) \
		--mtime=@$(SOURCE_DATE_EPOCH) \
		-C $(TARGET_DIR) $(GOOSE_FOLDER)

# Generate spec file and tarballs for build pipeline
spec: $(GOOSE_DIR)/.cargo-patched $(PATCHED_TARBALL) $(VENDORED_TARBALL)
	@echo "📄 Copying spec file to target"
	@mkdir -p $(TARGET_DIR)
	@cp packaging/$(NAME).spec $(TARGET_DIR)/$(NAME).spec
	@echo ""
	@echo "✅ Build artifacts ready in $(TARGET_DIR)/:"
	@echo "   - $(GOOSE_FOLDER)-patched.tar.zstd ($$(du -h $(PATCHED_TARBALL) | cut -f1))"
	@echo "   - $(GOOSE_FOLDER)-vendor.tar.zstd ($$(du -h $(VENDORED_TARBALL) | cut -f1))"
	@echo "   - $(NAME).spec"
	@echo ""
	@echo "💡 Ready for build!"

# Clean generated files
clean:
	@echo "Cleaning generated files"
	rm -rf $(TARGET_DIR)
	rm -rf packaging/$(GOOSE_DIR)-$(GOOSE_VERSION)*.tar*
	@echo "Clean complete"

# Debug target to show variables and check dependencies
debug:
	@echo "Variables:"
	@echo "  TAG=$(TAG)"
	@echo "  RUST_VERSION=$(RUST_VERSION)"
	@echo "  GOOSE_FOLDER=$(GOOSE_FOLDER)"
	@echo "  GOOSE_DIR=$(GOOSE_DIR)"
	@echo "  FULL_URL=$(FULL_URL)"
	@echo "  PATCHED_TARBALL=$(PATCHED_TARBALL)"
	@echo "  VENDORED_TARBALL=$(VENDORED_TARBALL)"
	@echo "  SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH)"
	@echo ""
	@echo "Dependencies:"
	@which cargo > /dev/null && echo "  ✓ cargo installed" || echo "  ✗ cargo not found"
	@which cargo-vendor-filterer > /dev/null && echo "  ✓ cargo-vendor-filterer installed" || echo "  ✗ cargo-vendor-filterer not found (install with: cargo install cargo-vendor-filterer)"
	@which dnf > /dev/null && echo "  ✓ dnf installed" || echo "  ✗ dnf not found"
	@which python3 > /dev/null && echo "  ✓ python3 installed" || echo "  ✗ python3 not found"
	@which tar > /dev/null && echo "  ✓ tar installed" || echo "  ✗ tar not found"
	@echo ""
	@echo "Files:"
	@[ -f packaging/goose.spec ] && echo "  ✓ packaging/goose.spec exists" || echo "  ✗ packaging/goose.spec not found"
	@[ -f check_fedora_deps.py ] && echo "  ✓ check_fedora_deps.py exists" || echo "  ✗ check_fedora_deps.py not found"
