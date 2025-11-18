# Goose Fedora/RHEL Packaging

Optimized packaging for [Goose](https://github.com/block/goose) - an open source AI agent.

## 🚀 Quick Start

### For Developers (Updating Dependencies)

```bash
# Update spec file and vendor filter
make check-deps TAG=1.13.1

# Review and commit
git diff packaging/goose.spec .cargo/vendor-filter.toml
git add packaging/goose.spec .cargo/vendor-filter.toml
git commit -m "Update to goose 1.13.1"
```

### For CI/CD (Building Packages)

```bash
# Generate optimized tarballs
make spec TAG=1.13.1

# Build artifacts are in target/
ls target/
```

## 📋 Two-Phase Workflow

### Phase 1: `make check-deps` (Developer)

Updates files for git commit:

```
┌──────────────────┐
│ make check-deps  │
└────────┬─────────┘
         │
         ├─> Downloads upstream source
         ├─> Checks Fedora repositories
         ├─> Updates packaging/goose.spec
         └─> Generates .cargo/vendor-filter.toml
         
✓ Commit these files to git
```

**What gets updated:**
- `packaging/goose.spec` - BuildRequires and Provides
- `.cargo/vendor-filter.toml` - Vendor exclusion list

### Phase 2: `make spec` (CI/CD)

Generates build artifacts using committed files:

```
┌──────────────────┐
│   make spec      │
└────────┬─────────┘
         │
         ├─> Downloads source
         ├─> Applies patches
         ├─> Uses .cargo/vendor-filter.toml
         ├─> Creates optimized vendor tarball (40-60% smaller!)
         └─> Creates patched source tarball
         
✓ Build artifacts in target/
```

**What gets generated:**
- `target/goose-X.Y.Z-patched.tar.zstd` - Patched source
- `target/goose-X.Y.Z-vendor.tar.zstd` - Optimized vendor deps
- `target/goose.spec` - Ready-to-build spec file

## 📦 Why This Approach?

### Traditional Approach
```
❌ Vendor ALL dependencies (~200 MB)
❌ Slow builds (compile everything)
❌ Manual spec file updates
```

### Our Optimized Approach
```
✅ Vendor ONLY missing deps (~80 MB, 60% smaller!)
✅ Fast builds (uses Fedora system packages)
✅ Automatic spec file updates
✅ Committed vendor filter (reproducible builds)
✅ Cached Fedora queries (fast reruns)
```

## 🛠️ Available Commands

| Command | Purpose | Who Uses It |
|---------|---------|-------------|
| `make check-deps TAG=X.Y.Z` | Update spec and vendor filter | Developer |
| `make spec TAG=X.Y.Z` | Generate build artifacts | CI/CD |
| `make download TAG=X.Y.Z` | Download upstream tarball only | Developer |
| `make clean` | Clean generated files | Anyone |
| `make help` | Show usage information | Anyone |

## 📁 Project Structure

```
goose/
├── .cargo/
│   └── vendor-filter.toml      # Committed - lists crates to exclude
├── packaging/
│   └── goose.spec              # Committed - RPM spec file
├── target/                     # Generated - build artifacts
│   ├── goose-X.Y.Z-patched.tar.zstd
│   ├── goose-X.Y.Z-vendor.tar.zstd
│   └── goose.spec
├── check_fedora_deps.py        # Committed - dependency checker
├── Makefile                    # Committed - build orchestration
└── PACKAGING_WORKFLOW.md       # Committed - detailed docs
```

## 🔄 Example Workflow

### Scenario: Update to Goose 1.14.0

```bash
# 1. Developer updates dependencies
make check-deps TAG=1.14.0

# Output:
# 🔍 Checking dependencies against Fedora repositories...
# ✅ Files updated:
#    - packaging/goose.spec (BuildRequires and Provides)
#    - .cargo/vendor-filter.toml (vendor exclusions)
# 
# 📝 Next steps:
#    1. Review changes: git diff packaging/goose.spec .cargo/vendor-filter.toml
#    2. Commit if satisfied: git add ... && git commit

# 2. Review what changed
git diff packaging/goose.spec .cargo/vendor-filter.toml

# Example changes:
# + BuildRequires: rust-new-crate-devel
# - Provides: bundled(crate(old-crate)) = 1.0.0

# 3. Commit the changes
git add packaging/goose.spec .cargo/vendor-filter.toml
git commit -m "Update to goose 1.14.0

- Added BuildRequires for newly-available crates
- Updated bundled crate versions
"

# 4. Push to trigger CI/CD
git push

# 5. CI/CD automatically runs:
# make spec TAG=1.14.0
# - Uses committed vendor-filter.toml
# - Generates optimized tarballs
# - Builds RPM packages
```

## 📊 Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Vendor Tarball** | ~200 MB (all deps) | ~80 MB (only missing deps) |
| **Spec File** | Manual updates | Automatic updates |
| **Build Time** | Slow (compile all) | Fast (use system packages) |
| **Maintenance** | High | Low |
| **Reproducibility** | Manual | Committed vendor filter |
| **Cache Support** | No | Yes (24h TTL) |

## 🔍 How It Works

### Dependency Checking

The `check_fedora_deps.py` script:

1. **Scans** all `Cargo.toml` files in the project
2. **Queries** Fedora repos with `dnf repoquery` (results cached)
3. **Determines** which crates are available in Fedora
4. **Updates** spec file:
   - `BuildRequires: rust-X-devel` for available crates
   - `Provides: bundled(crate(X)) = Y` for others
5. **Generates** vendor filter to exclude Fedora-available crates

### Optimized Vendoring

The vendor filter (`.cargo/vendor-filter.toml`) tells `cargo vendor-filterer`:

```toml
[exclude]
"anyhow" = "*"      # Available in Fedora
"chrono" = "*"      # Available in Fedora
"serde" = "*"       # Available in Fedora
# ... 80+ more crates
```

Result: Only vendor crates NOT available in Fedora!

## 🐛 Troubleshooting

### "No vendor filter found"

If you see this warning during `make spec`:

```bash
# Generate the filter first
make check-deps TAG=X.Y.Z
```

### Cache is stale

If Fedora repos were updated recently:

```bash
# Clear cache to get fresh data
./check_fedora_deps.py --clear-cache

# Then rerun
make check-deps TAG=X.Y.Z
```

### Preview before committing

Want to see changes without modifying files?

```bash
# Use draft mode
./check_fedora_deps.py --all-crates \
  --update-spec packaging/goose.spec \
  --generate-vendor-filter .cargo/vendor-filter.toml \
  --draft \
  target/goose-X.Y.Z.tar.gz
```

## 📚 Documentation

- **[PACKAGING_WORKFLOW.md](PACKAGING_WORKFLOW.md)** - Comprehensive workflow guide
- `make help` - Quick reference
- `./check_fedora_deps.py --help` - Script options

## 🤝 Contributing

When adding features:

1. Update dependencies: `make check-deps TAG=X.Y.Z`
2. Test the build: `make spec TAG=X.Y.Z`
3. Commit both spec and filter files
4. Submit PR with clear description

## 📝 License

This packaging infrastructure is part of the RHEL Lightspeed project.

---

**Questions?** See [PACKAGING_WORKFLOW.md](PACKAGING_WORKFLOW.md) for detailed documentation.

