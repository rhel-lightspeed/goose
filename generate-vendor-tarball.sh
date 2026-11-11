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

# Get a crate's version from Cargo.lock (first match).
crate_version() {
    local name="$1"
    awk -v name="$name" '
        /^\[\[package\]\]/ { pkg_name = ""; pkg_ver = "" }
        /^name = /         { gsub(/"/, ""); pkg_name = $3 }
        /^version = /      { gsub(/"/, ""); pkg_ver = $3 }
        pkg_name == name && pkg_ver != "" { print pkg_ver; exit }
    ' Cargo.lock
}

# Build versioned --exclude-crate-path entries from Cargo.lock.
# Must be called from inside the extracted source directory (where Cargo.lock lives).
build_crate_paths() {
    local ring_ver;    ring_ver=$(crate_version "ring")
    local onig_ver;    onig_ver=$(crate_version "onig_sys")
    local dbus_ver;    dbus_ver=$(crate_version "libdbus-sys")
    local sqlite_ver;  sqlite_ver=$(crate_version "libsqlite3-sys")
    local zstd_ver;    zstd_ver=$(crate_version "zstd-sys")
    local awslc_ver;   awslc_ver=$(crate_version "aws-lc-sys")
    local llama_ver;   llama_ver=$(crate_version "llama-cpp-sys-2")
    local secp_ver;    secp_ver=$(crate_version "secp256k1-sys")
    local ttf_ver;     ttf_ver=$(crate_version "ttf-parser")
    local vcpkg_ver;   vcpkg_ver=$(crate_version "vcpkg")

    CRATE_PATHS=(
        # Strip test directories from all crates (CI fixtures, not needed at build time)
        "*#tests"
        # onig_sys: bundled oniguruma C library (use system oniguruma-devel instead)
        "onig_sys-${onig_ver}#oniguruma"
        # libdbus-sys: bundled D-Bus C library (use system dbus-devel instead)
        "libdbus-sys-${dbus_ver}#vendor"
        # libsqlite3-sys: bundled SQLite C library (use system sqlite3-devel instead)
        "libsqlite3-sys-${sqlite_ver}#sqlite3"
        # libsqlite3-sys: bundled SQLCipher C library (use system sqlite3-devel instead)
        "libsqlite3-sys-${sqlite_ver}#sqlcipher"
        # ring: pre-generated platform object files (forbidden prebuilt binaries)
        "ring-${ring_ver}#pregenerated"
        # zstd-sys: bundled zstd C library (use system libzstd-devel instead)
        "zstd-sys-${zstd_ver}#zstd"
        # aws-lc-sys: bundled aws-lc C library (BoringSSL fork; forbidden, use system)
        "aws-lc-sys-${awslc_ver}#aws-lc"
        # aws-lc-sys: 26 pre-compiled Windows COFF .obj files (forbidden prebuilt binaries)
        "aws-lc-sys-${awslc_ver}#builder/prebuilt-nasm"
        # aws-lc-sys: pre-generated BoringSSL symbol prefix headers (~1.4 MB generated)
        "aws-lc-sys-${awslc_ver}#generated-include"
        # llama-cpp-sys-2: entire bundled llama.cpp + ggml + CUDA/Vulkan sources
        "llama-cpp-sys-2-${llama_ver}#llama.cpp"
        # secp256k1-sys: bundled libsecp256k1 C library (defensive; normally stripped by platform filtering)
        "secp256k1-sys-${secp_ver}#depend"
        # ttf-parser: Qt C++ developer tool shipped upstream, never compiled by cargo
        "ttf-parser-${ttf_ver}#testing-tools"
        # vcpkg: 341 zero-byte .dll/.lib/.a placeholder files used only for parser tests
        "vcpkg-${vcpkg_ver}#test-data"
    )
}

# Crates that Cargo's *dependency* resolver keeps in the lock graph even though
# they are never compiled for our feature set. reqwest declares
# `http2 = [..., "hyper-rustls?/http2"]`; weak (`dep?/feature`) references like
# this make `cargo metadata` (and therefore cargo-vendor-filterer) treat
# hyper-rustls as reachable, which drags in the whole rustls stack. The feature
# resolver used by the real build never activates them (verify with
# `cargo tree -p goose-cli -e normal,build,dev`), so we replace them with empty
# stubs the same way cargo-vendor-filterer stubs non-Linux crates. If the build
# ever starts using one of these for real, it fails loudly at compile time.
STUB_CRATES=(
    rustls
    hyper-rustls
    tokio-rustls
    rustls-webpki
)

# Replace a vendored crate directory with an empty stub: keep Cargo.toml (so
# dependencies/features still resolve) minus the build script and non-lib
# targets, an empty src/lib.rs, and a regenerated .cargo-checksum.json that
# keeps the original registry package checksum.
stub_crate() {
    local dir="$1"
    local pkg_sum
    pkg_sum=$(jq -r '.package' "$dir/.cargo-checksum.json")
    awk '
        /^\[\[(example|bench|test|bin)\]\]$/ { skip = 1; next }
        /^\[/                               { skip = 0 }
        skip                                { next }
        /^build = /                         { next }
        { print }
    ' "$dir/Cargo.toml" > "$dir/Cargo.toml.stub"
    find "$dir" -mindepth 1 -maxdepth 1 ! -name Cargo.toml.stub -exec rm -rf {} +
    mv "$dir/Cargo.toml.stub" "$dir/Cargo.toml"
    mkdir "$dir/src"
    : > "$dir/src/lib.rs"
    jq -n \
        --arg toml "$(sha256sum "$dir/Cargo.toml" | awk '{print $1}')" \
        --arg lib "$(sha256sum "$dir/src/lib.rs" | awk '{print $1}')" \
        --arg pkg "$pkg_sum" \
        '{files: {"Cargo.toml": $toml, "src/lib.rs": $lib}, package: $pkg}' \
        > "$dir/.cargo-checksum.json"
}

# Helper function to find out if the required tools are present.
check_required_tools() {
    # Ensure ~/.cargo/bin is in PATH (cargo install places binaries there)
    export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
    local tools=("make" "cargo" "rpmspec" "spectool" "tar" "patch" "curl" "jq")
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
# Folder for goose sources extracted from the release artifact tarball
# (upstream uses goose-vVERSION/ as the directory prefix in release artifacts)
GOOSE_SOURCE="$NAME-v$VERSION"
# Tarball for goose downloaded with spectool (release artifact naming)
GOOSE_SOURCE_TARBALL="$NAME-source-v$VERSION.tar.gz"

# Target platforms matching Fedora/EPEL/RHEL build architectures
PLATFORMS=(
    x86_64-unknown-linux-gnu
    aarch64-unknown-linux-gnu
    s390x-unknown-linux-gnu
    powerpc64le-unknown-linux-gnu
)


# Features read directly from the spec's downstream_features global so this
# script and the RPM build can never drift out of sync.
FEATURES=$(awk '/^%global downstream_features/{print $3}' goose.spec)


if [ ! -f "$GOOSE_SOURCE_TARBALL" ]; then
    echo "[!] Tarball missing, downloading with spectool..."
    run make sources
fi

echo "[+] Verifying tarball integrity against GitHub release digest..."
# Since goose >= 1.45.0, upstream publishes immutable source archives as GitHub
# release artifacts with a sha256 digest. We fetch the digest from the GitHub
# Releases API and verify the downloaded tarball against it. This protects
# against tag-force-move attacks on the upstream repository.
# See: https://redhat.atlassian.net/browse/RSPEED-3446
GITHUB_API_URL="https://api.github.com/repos/aaif-goose/goose/releases/tags/v${VERSION}"
JQ_FILTER=".assets[] | select(.name == \"${GOOSE_SOURCE_TARBALL}\") | .digest"
EXPECTED_SHA256=$(
    curl -sfL "$GITHUB_API_URL" \
        | jq -r "$JQ_FILTER" \
        | sed 's/^sha256://'
) || true

if [ -z "$EXPECTED_SHA256" ]; then
    echo "[-] ERROR: Could not retrieve SHA256 digest for $GOOSE_SOURCE_TARBALL from GitHub release v${VERSION}"
    echo "[-]        Verify the release exists and contains the source artifact."
    exit 1
fi

ACTUAL_SHA256=$(sha256sum "$GOOSE_SOURCE_TARBALL" | awk '{print $1}')
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "[-] ERROR: SHA256 checksum mismatch for $GOOSE_SOURCE_TARBALL"
    echo "[-]   Expected: $EXPECTED_SHA256"
    echo "[-]   Actual:   $ACTUAL_SHA256"
    exit 1
fi
echo "[+] SHA256 verified: $ACTUAL_SHA256"

echo "[+] Tarball verified, extracting..."
# We remove vendor folder to avoid conflicts with ``cargo vendor-filterer`
rm -rf "$GOOSE_SOURCE" && run tar -xzf "$GOOSE_SOURCE_TARBALL" --exclude "${GOOSE_SOURCE}/vendor"

echo "[+] Applying patches..."
pushd "$GOOSE_SOURCE" >/dev/null
for patch in "${PATCHES[@]}"; do
    run patch -p1 <"../$patch"
    echo "[!]   Applied patch $patch"
done

echo "[+] Generating vendor folder (Linux-only via cargo-vendor-filterer)..."
build_crate_paths

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
    vendor

echo "[+] Stubbing crates that are resolved but never compiled..."
for crate in "${STUB_CRATES[@]}"; do
    # Exact "<name>-<version>" match so e.g. "rustls" does not hit "rustls-webpki".
    matches=()
    for dir in vendor/"${crate}"-[0-9]*/; do
        [ -d "$dir" ] && matches+=("${dir%/}")
    done
    if [ ${#matches[@]} -eq 0 ]; then
        echo "[!]   $crate not vendored anymore; remove it from STUB_CRATES"
        continue
    fi
    for dir in "${matches[@]}"; do
        stub_crate "$dir"
        echo "[!]   Stubbed $dir"
    done
done

echo "[+] Creating vendor tarball..."
# Deterministic archive: sorted entries, fixed ownership and timestamps.
run tar --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="@${SOURCE_DATE_EPOCH:-0}" \
    --zstd -cf "../${NAME}-${VERSION}-vendor.tar.zstd" vendor

popd >/dev/null

echo "[++] All done!"
