#!/bin/bash
set -euo pipefail

# When VERBOSE=1 all subprocess output is shown. The default (0) silences
# noisy tools (cargo, patch, spectool, tar) while keeping echo messages visible.
VERBOSE=${VERBOSE:-0}

# Run a command, suppressing its stdout/stderr unless VERBOSE=1.
run() {
    if [ "$VERBOSE" -eq 1 ]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi
}

# Helper function to find out if the required tools are present.
check_required_tools() {
    # Ensure ~/.cargo/bin is in PATH (cargo install places binaries there)
    export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
    local tools=("make" "cargo" "rpmspec" "spectool" "tar" "patch")
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

# Dependency patches (0001-0019) applied to the vendored source tree.
# These are Cargo.toml patches that affect dependency resolution and therefore
# determine which crates need to be vendored. Feature flag selection is handled
# via --no-default-features --features passed to cargo vendor-filterer directly.
# Discovered automatically by glob so adding/removing a patch file is enough.
PATCHES=()
while IFS= read -r patch; do
    PATCHES+=("$patch")
done < <(ls 000[0-9]-*.patch 001[0-9]-*.patch 2>/dev/null | sort)

# Grab the name from the specfile
NAME=$(rpmspec -q --qf "%{NAME}" goose.spec)
# Grab the version from the specfile
VERSION=$(rpmspec -q --qf "%{VERSION}" goose.spec)
# Folder for goose sources extracted from tarball
GOOSE_SOURCE="$NAME-$VERSION"
# Tarball for goose downloaded with spectool
GOOSE_SOURCE_TARBALL="$GOOSE_SOURCE.tar.gz"

# Target platforms matching Fedora/EPEL/RHEL build architectures
PLATFORMS=(
    x86_64-unknown-linux-gnu
    aarch64-unknown-linux-gnu
    s390x-unknown-linux-gnu
    powerpc64le-unknown-linux-gnu
)

# Paths excluded from the vendor tarball. Each entry removes content that is
# either a bundled C/C++ library, pre-built binary, or test/tool data that is
# forbidden or unnecessary in a Fedora source package.
CRATE_PATHS=(
    # Strip test directories from all crates (CI fixtures, not needed at build time)
    "*#tests"
    # onig_sys: bundled oniguruma C library (use system oniguruma-devel instead)
    "onig_sys#oniguruma"
    # libdbus-sys: bundled D-Bus C library (use system dbus-devel instead)
    "libdbus-sys#vendor"
    # libsqlite3-sys: bundled SQLite C library (use system sqlite3-devel instead)
    "libsqlite3-sys#sqlite3"
    # libsqlite3-sys: bundled SQLCipher C library (use system sqlite3-devel instead)
    "libsqlite3-sys#sqlcipher"
    # ring: pre-generated platform object files (forbidden prebuilt binaries)
    "ring#pregenerated"
    # zstd-sys: bundled zstd C library (use system libzstd-devel instead)
    "zstd-sys#zstd"
    # aws-lc-sys: bundled aws-lc C library (BoringSSL fork; forbidden, use system)
    "aws-lc-sys#aws-lc"
    # aws-lc-sys: 26 pre-compiled Windows COFF .obj files (forbidden prebuilt binaries)
    "aws-lc-sys#builder/prebuilt-nasm"
    # aws-lc-sys: pre-generated BoringSSL symbol prefix headers (~1.4 MB generated)
    "aws-lc-sys#generated-include"
    # llama-cpp-sys-2: entire bundled llama.cpp + ggml + CUDA/Vulkan sources
    "llama-cpp-sys-2#llama.cpp"
    # secp256k1-sys: bundled libsecp256k1 C library (defensive; normally stripped by platform filtering)
    "secp256k1-sys#depend"
    # ttf-parser: Qt C++ developer tool shipped upstream, never compiled by cargo
    "ttf-parser#testing-tools"
    # vcpkg: 341 zero-byte .dll/.lib/.a placeholder files used only for parser tests
    "vcpkg#test-data"
)

# Features read directly from the spec's downstream_features global so this
# script and the RPM build can never drift out of sync.
FEATURES=$(awk '/^%global downstream_features/{print $3}' goose.spec)


if [ ! -f "$GOOSE_SOURCE_TARBALL" ]; then
    echo "[!] Tarball missing, downloading with spectool..."
    run make sources
fi

echo "[+] Extracting tarball..."
# We remove vendor folder to avoid conflicts with ``cargo vendor-filterer`
rm -rf "$GOOSE_SOURCE" && run tar -xzf "$GOOSE_SOURCE_TARBALL" --exclude "goose-${VERSION}/vendor"

echo "[+] Applying patches..."
pushd "$GOOSE_SOURCE" >/dev/null
for patch in "${PATCHES[@]}"; do
    run patch -p1 <"../$patch"
    echo "[!]   Applied patch $patch"
done

echo "[+] Generating vendor folder (Linux-only via cargo-vendor-filterer)..."
PLATFORM_ARGS=()
for platform in "${PLATFORMS[@]}"; do
    PLATFORM_ARGS+=("--platform=$platform")
done

EXCLUDE_ARGS=()
for crate_path in "${CRATE_PATHS[@]}"; do
    EXCLUDE_ARGS+=("--exclude-crate-path=$crate_path")
done

# --no-default-features disables upstream defaults that would pull in forbidden
# content (rustls, aws-lc-rs via aws-providers). --features mirrors the feature
# set used in %cargo_build and %cargo_test so the vendor tarball contains exactly
# what is needed to build the downstream package.
run cargo vendor-filterer --tier=2 "${PLATFORM_ARGS[@]}" \
    --no-default-features \
    --features "${FEATURES}" \
    --versioned-dirs \
    "${EXCLUDE_ARGS[@]}" \
    --prefix vendor \
    --format=tar.zstd

echo "[+] Moving vendor tarball to repo root..."
mv vendor.tar.zstd "../${NAME}-${VERSION}-vendor.tar.zstd"

popd >/dev/null

echo "[++] All done!"
