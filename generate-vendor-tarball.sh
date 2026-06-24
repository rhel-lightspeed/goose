#!/bin/bash
set -euo pipefail

# List of patches to be applied in the vendored folder
PATCHES=(
    "0001-Strip-non-Linux-deps-and-use-system-libraries.patch"
    "0002-Set-downstream-feature-flags.patch"
)

check_required_tools() {
    local tools=("cargo" "rpmspec" "spectool" "tar" "patch")
    local missing=()

    for tool in "${tools[@]}"; do
        command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
    done

    if [ ${#missing[@]} -ne 0 ]; then
        echo "ERROR: Missing required tools: ${missing[*]}"
        exit 1
    fi
}

check_required_tools

# Grab the name from the specfile
NAME=$(rpmspec -q --qf "%{NAME}" goose.spec)
# Grab the version from the specfile
VERSION=$(rpmspec -q --qf "%{VERSION}" goose.spec)
# Folder for goose sources extracted from tarball
GOOSE_SOURCE="$NAME-$VERSION"
# Tarball for goose downloaded with spectool
GOOSE_SOURCE_TARBALL="$GOOSE_SOURCE.tar.gz"

if [ ! -f "$GOOSE_SOURCE_TARBALL" ]; then
    echo "[!] Tarball missing, downloading with spectool..."
    spectool -g goose.spec >/dev/null 2>&1 || {
        echo "[-] ERROR: spectool failed"
        exit 1
    }
fi

echo "[+] Tarball found, extracting..."
rm -rf "$GOOSE_SOURCE"
tar -xzf "$GOOSE_SOURCE_TARBALL" \
    --exclude "goose-${VERSION}/.claude" \
    --exclude "goose-${VERSION}/.codex" \
    --exclude "goose-${VERSION}/.cursor" \
    --exclude "goose-${VERSION}/evals" \
    --exclude "goose-${VERSION}/services" \
    --exclude "goose-${VERSION}/oidc-proxy" \
    --exclude "goose-${VERSION}/vendor/v8"

echo "[+] Applying patches..."
pushd "$GOOSE_SOURCE" >/dev/null
for patch in "${PATCHES[@]}"; do
    patch -p1 <"../$patch"
    echo "[!] Applied patch $patch"
done

# Target platforms matching Fedora/EPEL build architectures
PLATFORMS=(
    x86_64-unknown-linux-gnu
    aarch64-unknown-linux-gnu
    s390x-unknown-linux-gnu
    powerpc64le-unknown-linux-gnu
)

PLATFORM_ARGS=()
for platform in "${PLATFORMS[@]}"; do
    PLATFORM_ARGS+=("--platform=$platform")
done

# Ensure ~/.cargo/bin is in PATH (cargo install places binaries there)
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"

# Remove the in-tree vendor/v8 shim to avoid conflicts with cargo-vendor-filterer
rm -rf vendor

echo "[+] Generating vendor folder (Linux-only via cargo-vendor-filterer)..."
cargo vendor-filterer "${PLATFORM_ARGS[@]}" --versioned-dirs

echo "[+] Generating tarball of vendor folder..."
tar Jcf "../$NAME-$VERSION-vendor.tar.xz" vendor/ >/dev/null 2>&1

echo "[+] Cleaning up..."
rm -rf "$GOOSE_SOURCE" "$GOOSE_SOURCE_TARBALL"

popd >/dev/null
echo "[++] All done!"
