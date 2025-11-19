#!/bin/bash
# Script to remove Fedora-available packages from vendor tarball
# Usage: ./remove-fedora-packages.sh <full-tarball> <output-tarball> <spec-file> [temp-dir]

set -euo pipefail

FULL_TARBALL="$1"
OUTPUT_TARBALL="$2"
SPEC_FILE="$3"
TEMP_DIR="${4:-$(mktemp -d)}"
CLEANUP_TEMP=false

if [ $# -lt 4 ]; then
    CLEANUP_TEMP=true
fi

echo "🧹 Removing Fedora-available packages from vendor tarball..."
echo "   📂 Input: $FULL_TARBALL"
echo "   📂 Output: $OUTPUT_TARBALL"

# Create temp directory and extract
mkdir -p "$TEMP_DIR"
echo "   📦 Extracting vendor tarball..."
tar --zstd -xf "$FULL_TARBALL" -C "$TEMP_DIR"

# Count packages before
TOTAL_BEFORE=$(find "$TEMP_DIR/vendor" -maxdepth 1 -type d | wc -l)
echo "   📊 Total packages before cleanup: $TOTAL_BEFORE"

# Extract package names from spec file and remove them
echo "   🔍 Scanning spec file for Fedora packages..."
REMOVED=0

while IFS= read -r pkg; do
    # Skip empty lines
    [ -z "$pkg" ] && continue
    
    # Also try with underscores instead of hyphens
    pkg_underscore=$(echo "$pkg" | tr '-' '_')
    
    # Find and remove matching directories
    # Match only exact package name followed by version (e.g., axum-0.7.9, not axum-core-0.4.0)
    # Versions start with a digit, so we use patterns like pkg-[0-9]*
    found=$(find "$TEMP_DIR/vendor" -maxdepth 1 -type d \( -name "${pkg}-[0-9]*" -o -name "${pkg}" \) 2>/dev/null || true)
    
    if [ -n "$found" ]; then
        while IFS= read -r dir; do
            [ -z "$dir" ] && continue
            basename_dir=$(basename "$dir")
            echo "      Removing: $basename_dir"
            rm -rf "$dir"
            REMOVED=$((REMOVED + 1))
        done <<< "$found"
    fi
done < <(grep -E '^BuildRequires:\s+rust-.*-devel' "$SPEC_FILE" | \
         sed -E 's/^BuildRequires:\s+rust-(.+)-devel$/\1/')


# Count packages after
TOTAL_AFTER=$(find "$TEMP_DIR/vendor" -maxdepth 1 -type d | wc -l)
echo "   🗑️  Removed $REMOVED package directories"
echo "   📊 Remaining packages: $TOTAL_AFTER"

# Recompress the cleaned vendor directory
echo "   📦 Recompressing vendor tarball..."

# Get SOURCE_DATE_EPOCH from git or use current time
if [ -d "$(dirname "$FULL_TARBALL")/../.git" ]; then
    SOURCE_DATE_EPOCH=$(git -C "$(dirname "$FULL_TARBALL")/.." log -1 --pretty=%ct 2>/dev/null || date +%s)
else
    SOURCE_DATE_EPOCH=$(date +%s)
fi

tar --zstd -cf "$OUTPUT_TARBALL" \
    --sort=name --owner=0 --group=0 --numeric-owner \
    --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
    --mtime="@${SOURCE_DATE_EPOCH}" \
    -C "$TEMP_DIR" vendor

# Cleanup
if [ "$CLEANUP_TEMP" = true ]; then
    rm -rf "$TEMP_DIR"
fi

echo "   ✅ Cleaned vendor tarball created: $(du -h "$OUTPUT_TARBALL" | cut -f1)"

