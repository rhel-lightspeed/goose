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
FULL_URL := $(UPSTREAM_REPOSITORY)$(TAG).tar.gz

# Get source date epoch from extracted git repo
SOURCE_DATE_EPOCH = $(shell cd $(GOOSE_DIR) && git log -1 --pretty=%ct 2>/dev/null || date +%s)

.PHONY: spec clean help

all: help

help:
	@echo "Available targets:"
	@echo "  spec           - Generate RPM spec file"
	@echo "  clean          - Clean generated files"
	@echo ""
	@echo "Variables:"
	@echo "  TAG=$(TAG)"
	@echo "  RUST_VERSION=$(RUST_VERSION)"

# Download upstream goose
$(TARGET_DIR)/$(GOOSE_TARBALL):
	@echo "🚀 Packaging Goose v$(TAG) with Rust $(RUST_VERSION)"
	@mkdir -p $(TARGET_DIR)
	@echo "📥 Downloading goose from $(FULL_URL)"
	curl -L "$(FULL_URL)" -o $@

# Extract tarball
$(GOOSE_DIR)/.extracted: $(TARGET_DIR)/$(GOOSE_TARBALL)
	@echo "📦 Extracting tarball"
	tar xf $< -C $(TARGET_DIR)
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
$(GOOSE_DIR)/.rust-toolchain-patched: $(GOOSE_DIR)/.extracted
	@echo "🔧 Updating rust-toolchain.toml to version $(RUST_VERSION)"
	@if [ -f $(GOOSE_DIR)/rust-toolchain.toml ]; then \
		sed -i 's/channel = "[^"]*"/channel = "$(RUST_VERSION)"/' $(GOOSE_DIR)/rust-toolchain.toml; \
	fi
	@touch $@

# Vendor dependencies - creates both tarball and config
$(VENDORED_TARBALL): $(GOOSE_DIR)/.rust-toolchain-patched
	@echo "📦 Vendoring dependencies"
	@mkdir -p $(GOOSE_DIR)/.cargo
	@cd $(GOOSE_DIR) && \
		cargo vendor-filterer --prefix=vendor --format=tar.zstd ../$(notdir $@) | \
		sed 's|directory = ".*"|directory = "vendor"|' > .cargo/vendor-config.toml
	@touch $(GOOSE_DIR)/.cargo/vendor-config.toml

# Create patched tarball with reproducible options
$(PATCHED_TARBALL): $(GOOSE_DIR)/.rust-toolchain-patched $(GOOSE_DIR)/.extracted
	@echo "📦 Creating patched goose tarball"
	tar --zstd -cvf $@ $(TAR_REPRODUCIBLE_OPTS) \
		--mtime=@$(SOURCE_DATE_EPOCH) \
		-C $(TARGET_DIR) $(GOOSE_FOLDER)

# Generate spec file
vendor-spec: $(PATCHED_TARBALL) $(VENDORED_TARBALL) $(VENDORED_TARBALL)
	@echo "Generating spec file"
	@mkdir -p $(TARGET_DIR)
	@sed -e 's/^Version:.*/# Replaced by make spec\nVersion: $(TAG)/' \
		-e 's/^Source0:.*/Source0: $(GOOSE_FOLDER)-patched.tar.zstd/' \
		-e 's/^Source1:.*/Source1: $(GOOSE_FOLDER)-vendor.tar.zstd/' \
		packaging/$(NAME).spec > $(TARGET_DIR)/$(NAME).spec
	@echo "Generated: $(TARGET_DIR)/$(NAME).spec"
	@rm -rf $(GOOSE_DIR) $(GOOSE_TARBALL)

# Generate spec file
spec: $(PATCHED_TARBALL)
	@echo "Generating spec file"
	@mkdir -p $(TARGET_DIR)
	@sed -e 's/^Version:.*/# Replaced by make spec\nVersion: $(TAG)/' \
		-e 's/^Source0:.*/Source0: $(GOOSE_FOLDER)-patched.tar.zstd/' \
		packaging/$(NAME).spec > $(TARGET_DIR)/$(NAME).spec
	@echo "Generated: $(TARGET_DIR)/$(NAME).spec"
	@rm -rf $(GOOSE_DIR) $(GOOSE_TARBALL)

# Clean generated files
clean:
	@echo "Cleaning generated files"
	rm -rf $(TARGET_DIR)
	rm -rf packaging/$(GOOSE_DIR)-$(GOOSE_VERSION)*.tar*
	@echo "Clean complete"

# Debug target to show variables
debug:
	@echo "TAG=$(TAG)"
	@echo "RUST_VERSION=$(RUST_VERSION)"
	@echo "GOOSE_FOLDER=$(GOOSE_FOLDER)"
	@echo "GOOSE_DIR=$(GOOSE_DIR)"
	@echo "FULL_URL=$(FULL_URL)"
	@echo "PATCHED_TARBALL=$(PATCHED_TARBALL)"
	@echo "VENDORED_TARBALL=$(VENDORED_TARBALL)"
	@echo "SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH)"
