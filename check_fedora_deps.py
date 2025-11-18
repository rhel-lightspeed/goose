#!/usr/bin/env python3
"""
Check if Rust crate dependencies from goose tarball exist in Fedora.

This script:
1. Extracts the goose tarball
2. Parses Cargo.toml and Cargo.lock files to find all dependencies
3. Checks if each dependency exists in Fedora repositories
4. Generates a comprehensive report
"""

import argparse
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


class CargoParser:
    """Parse Cargo.toml and Cargo.lock files to extract dependencies."""
    
    def __init__(self, source_dir: Path):
        self.source_dir = source_dir
        self.cargo_toml_path = source_dir / "Cargo.toml"
        self.cargo_lock_path = source_dir / "Cargo.lock"
    
    def find_all_cargo_tomls(self) -> List[Path]:
        """Find all Cargo.toml files in the project."""
        cargo_tomls = []
        
        # Always include the root Cargo.toml
        if self.cargo_toml_path.exists():
            cargo_tomls.append(self.cargo_toml_path)
        
        # Search for Cargo.toml files in subdirectories
        for cargo_file in self.source_dir.rglob("Cargo.toml"):
            if cargo_file != self.cargo_toml_path and cargo_file not in cargo_tomls:
                cargo_tomls.append(cargo_file)
        
        return sorted(cargo_tomls)
    
    def parse_single_cargo_toml(self, cargo_path: Path) -> Set[str]:
        """Extract direct dependencies from a single Cargo.toml file."""
        dependencies = set()
        
        if not cargo_path.exists():
            return dependencies
        
        with open(cargo_path, 'r') as f:
            content = f.read()
        
        # Parse [dependencies], [dev-dependencies], [build-dependencies] sections
        in_deps_section = False
        section_pattern = re.compile(r'^\[(.*dependencies.*)\]')
        dep_pattern = re.compile(r'^([a-zA-Z0-9_-]+)\s*=')
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Check if we're entering a dependencies section
            section_match = section_pattern.match(line)
            if section_match:
                section_name = section_match.group(1)
                in_deps_section = 'dependencies' in section_name.lower()
                continue
            
            # Check if we're leaving the section
            if line.startswith('[') and in_deps_section:
                in_deps_section = False
                continue
            
            # Extract dependency name
            if in_deps_section and line and not line.startswith('#'):
                dep_match = dep_pattern.match(line)
                if dep_match:
                    dep_name = dep_match.group(1)
                    dependencies.add(dep_name)
        
        return dependencies
    
    def parse_cargo_toml(self) -> Set[str]:
        """Extract direct dependencies from root Cargo.toml."""
        return self.parse_single_cargo_toml(self.cargo_toml_path)
    
    def parse_cargo_lock(self) -> Dict[str, str]:
        """Extract all dependencies (including transitive) from Cargo.lock."""
        dependencies = {}
        
        if not self.cargo_lock_path.exists():
            print(f"Warning: {self.cargo_lock_path} not found")
            return dependencies
        
        with open(self.cargo_lock_path, 'r') as f:
            content = f.read()
        
        # Parse TOML format Cargo.lock
        # Look for [[package]] sections
        package_pattern = re.compile(r'\[\[package\]\]')
        name_pattern = re.compile(r'^name\s*=\s*"([^"]+)"')
        version_pattern = re.compile(r'^version\s*=\s*"([^"]+)"')
        
        current_name = None
        current_version = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            if package_pattern.match(line):
                # Save previous package if we have one
                if current_name and current_version:
                    dependencies[current_name] = current_version
                current_name = None
                current_version = None
                continue
            
            name_match = name_pattern.match(line)
            if name_match:
                current_name = name_match.group(1)
                continue
            
            version_match = version_pattern.match(line)
            if version_match:
                current_version = version_match.group(1)
                continue
        
        # Don't forget the last package
        if current_name and current_version:
            dependencies[current_name] = current_version
        
        return dependencies
    
    def get_all_dependencies(self) -> Dict[str, str]:
        """Get all dependencies from both Cargo.toml and Cargo.lock."""
        # Get all deps from Cargo.lock (most comprehensive)
        all_deps = self.parse_cargo_lock()
        
        # Also check Cargo.toml for any additional context
        direct_deps = self.parse_cargo_toml()
        
        return all_deps
    
    def get_direct_dependencies(self) -> Dict[str, str]:
        """Get only direct (top-level) dependencies from Cargo.toml with versions from Cargo.lock."""
        direct_deps = self.parse_cargo_toml()
        all_deps_with_versions = self.parse_cargo_lock()
        
        # Match direct deps with their versions from Cargo.lock
        result = {}
        for dep_name in direct_deps:
            if dep_name in all_deps_with_versions:
                result[dep_name] = all_deps_with_versions[dep_name]
            else:
                result[dep_name] = "unknown"
        
        return result
    
    def get_all_direct_dependencies_with_sources(self) -> Dict[str, Tuple[str, List[str]]]:
        """
        Get direct dependencies from all Cargo.toml files with their sources.
        
        Returns:
            Dict mapping dependency name to (version, [source_files])
        """
        all_cargo_files = self.find_all_cargo_tomls()
        all_deps_with_versions = self.parse_cargo_lock()
        
        # Track which dependencies come from which Cargo.toml files
        dep_sources = defaultdict(list)
        
        for cargo_file in all_cargo_files:
            deps = self.parse_single_cargo_toml(cargo_file)
            # Get a nice relative path for display
            rel_path = cargo_file.relative_to(self.source_dir)
            
            for dep_name in deps:
                dep_sources[dep_name].append(str(rel_path))
        
        # Combine with version information
        result = {}
        for dep_name, sources in dep_sources.items():
            version = all_deps_with_versions.get(dep_name, "unknown")
            result[dep_name] = (version, sources)
        
        return result


class CacheManager:
    """Manage persistent cache for Fedora package queries."""
    
    def __init__(self, cache_file: Optional[Path] = None, cache_ttl: int = 86400):
        """
        Initialize cache manager.
        
        Args:
            cache_file: Path to cache file (default: ~/.cache/goose-fedora-deps.json)
            cache_ttl: Cache time-to-live in seconds (default: 24 hours)
        """
        if cache_file is None:
            cache_dir = Path.cwd() / ".cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_file = cache_dir / "goose-fedora-deps.json"
        else:
            self.cache_file = cache_file
        
        self.cache_ttl = cache_ttl
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                # Validate cache structure
                if isinstance(data, dict) and "entries" in data:
                    return data
                return {}
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache: {e}", file=sys.stderr)
    
    def get(self, crate_name: str) -> Optional[Tuple[bool, str, List[str]]]:
        """Get cached result for a crate."""
        if "entries" not in self.cache:
            self.cache["entries"] = {}
        
        if crate_name not in self.cache["entries"]:
            return None
        
        entry = self.cache["entries"][crate_name]
        timestamp = entry.get("timestamp", 0)
        
        # Check if cache entry is still valid
        if time.time() - timestamp > self.cache_ttl:
            return None
        
        return (entry["exists"], entry["message"], entry["packages"])
    
    def set(self, crate_name: str, exists: bool, message: str, packages: List[str]):
        """Cache result for a crate."""
        if "entries" not in self.cache:
            self.cache["entries"] = {}
        
        self.cache["entries"][crate_name] = {
            "exists": exists,
            "message": message,
            "packages": packages,
            "timestamp": time.time()
        }
    
    def save(self):
        """Persist cache to disk."""
        self._save_cache()
    
    def clear(self):
        """Clear all cache entries."""
        self.cache = {}
        self._save_cache()


class FedoraChecker:
    """Check if Rust crates exist in Fedora repositories."""
    
    def __init__(self, quiet: bool = False, cache_manager: Optional[CacheManager] = None):
        self.quiet = quiet
        self.cache_manager = cache_manager
        self.session_cache = {}
    
    def check_crate(self, crate_name: str) -> Tuple[bool, str, List[str]]:
        """
        Check if a crate exists in Fedora.
        
        Returns:
            Tuple of (exists, message, packages_list)
        """
        # Check session cache first
        if crate_name in self.session_cache:
            return self.session_cache[crate_name]
        
        # Check persistent cache
        if self.cache_manager:
            cached_result = self.cache_manager.get(crate_name)
            if cached_result is not None:
                self.session_cache[crate_name] = cached_result
                return cached_result
        
        # Fedora packages Rust crates with the pattern: rust-{crate-name}-devel
        # They also provide virtual packages like: rust({crate-name})
        
        # Try both patterns
        patterns = [
            f"rust({crate_name})",
            f"rust-{crate_name}-devel",
        ]
        
        for pattern in patterns:
            try:
                cmd = ["dnf", "repoquery", "--quiet", "--whatprovides", pattern]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    packages = result.stdout.strip().split('\n')
                    # Clean up package names and sort them
                    packages = [pkg.strip() for pkg in packages if pkg.strip()]
                    msg = f"✓ {packages[0]}"
                    result = (True, msg, packages)
                    self._cache_result(crate_name, *result)
                    return result
            
            except subprocess.TimeoutExpired:
                msg = "⚠ Timeout while querying Fedora repos"
                result = (False, msg, [])
                self._cache_result(crate_name, *result)
                return result
            except Exception as e:
                msg = f"⚠ Error: {str(e)}"
                result = (False, msg, [])
                self._cache_result(crate_name, *result)
                return result
        
        msg = "✗ Not found in Fedora"
        result = (False, msg, [])
        self._cache_result(crate_name, *result)
        return result
    
    def _cache_result(self, crate_name: str, exists: bool, message: str, packages: List[str]):
        """Cache a result in both session and persistent cache."""
        result = (exists, message, packages)
        self.session_cache[crate_name] = result
        if self.cache_manager:
            self.cache_manager.set(crate_name, exists, message, packages)

class SpecFileUpdater:
    """Update RPM spec file with BuildRequires and Provides."""
    
    def __init__(self, spec_file: Path):
        self.spec_file = spec_file
        if not self.spec_file.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_file}")
    
    def update_spec(self, dependencies: Dict[str, str], 
                   results: Dict[str, Tuple[bool, str, List[str]]],
                   draft: bool = False) -> str:
        """
        Update spec file with BuildRequires and Provides.
        
        Returns:
            String with the changes summary or preview
        """
        with open(self.spec_file, 'r') as f:
            lines = f.readlines()
        
        # Find the sections to update
        buildrequires_idx = self._find_buildrequires_section(lines)
        provides_idx = self._find_provides_section(lines)
        
        # Separate dependencies into found (BuildRequires) and missing (Provides)
        build_requires = []
        provides = []
        
        for name, version in sorted(dependencies.items()):
            exists, msg, packages = results[name]
            if exists:
                build_requires.append(f"BuildRequires: rust-{name}-devel\n")
            else:
                # Goose crates are not a bundle, as they are built and linked together
                if name in ["goose", "goose-bench", "goose-mcp"]:
                    continue
                provides.append(f"Provides: bundled(crate({name})) = {version}\n")
        
        # Generate preview
        preview = self._generate_preview(build_requires, provides)
        
        if draft:
            return preview
        
        # Update the file
        new_lines = self._update_lines(lines, buildrequires_idx, provides_idx, 
                                      build_requires, provides)
        
        # Write the updated file
        with open(self.spec_file, 'w') as f:
            f.writelines(new_lines)
        
        return preview
    
    def _find_buildrequires_section(self, lines: List[str]) -> Tuple[int, int]:
        """Find the markers for Rust dependencies section."""
        start_idx = -1
        end_idx = -1
        
        for i, line in enumerate(lines):
            if '# Rust dependencies' in line:
                start_idx = i
            elif '# End rust dependencies' in line:
                end_idx = i
                break
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("Could not find '# Rust dependencies' markers in spec file")
        
        return (start_idx, end_idx)
    
    def _find_provides_section(self, lines: List[str]) -> Tuple[int, int]:
        """Find the markers for bundled dependencies section."""
        start_idx = -1
        end_idx = -1
        
        for i, line in enumerate(lines):
            if '# Bundled dependencies' in line:
                start_idx = i
            elif '# End bundled dependencies' in line:
                end_idx = i
                break
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("Could not find '# Bundled dependencies' markers in spec file")
        
        return (start_idx, end_idx)
    
    def _update_lines(self, lines: List[str], buildrequires_idx: Tuple[int, int],
                     provides_idx: Tuple[int, int], build_requires: List[str],
                     provides_list: List[str]) -> List[str]:
        """Update the lines with new BuildRequires and Provides using markers."""
        new_lines = []
        br_start, br_end = buildrequires_idx
        prov_start, prov_end = provides_idx
        
        i = 0
        while i < len(lines):
            # Handle Rust dependencies section
            if i == br_start:
                # Add the start marker
                new_lines.append(lines[i])
                i += 1
                # Skip everything between markers
                while i < br_end:
                    i += 1
                # Add the BuildRequires
                for br in build_requires:
                    new_lines.append(br)
                # Add the end marker
                new_lines.append(lines[br_end])
                i = br_end + 1
                continue
            
            # Handle Bundled dependencies section
            if i == prov_start:
                # Add the start marker
                new_lines.append(lines[i])
                i += 1
                # Skip everything between markers
                while i < prov_end:
                    i += 1
                # Add the Provides
                for prov in provides_list:
                    new_lines.append(prov)
                # Add the end marker
                new_lines.append(lines[prov_end])
                i = prov_end + 1
                continue
            
            # Copy other lines as-is
            new_lines.append(lines[i])
            i += 1
        
        return new_lines
    
    def _generate_preview(self, build_requires: List[str], provides: List[str]) -> str:
        """Generate a preview of changes."""
        preview = "\n" + "="*80 + "\n"
        preview += "SPEC FILE UPDATE PREVIEW\n"
        preview += "="*80 + "\n\n"
        
        if build_requires:
            preview += f"📦 BuildRequires to add ({len(build_requires)}):\n"
            preview += "-" * 80 + "\n"
            for br in build_requires[:10]:  # Show first 10
                preview += f"  {br.strip()}\n"
            if len(build_requires) > 10:
                preview += f"  ... and {len(build_requires) - 10} more\n"
            preview += "\n"
        
        if provides:
            preview += f"📦 Provides (bundled) to add ({len(provides)}):\n"
            preview += "-" * 80 + "\n"
            for prov in provides[:10]:  # Show first 10
                preview += f"  {prov.strip()}\n"
            if len(provides) > 10:
                preview += f"  ... and {len(provides) - 10} more\n"
            preview += "\n"
        
        preview += "="*80 + "\n"
        return preview


class TarballExtractor:
    """Extract goose tarball to a temporary directory."""
    
    def __init__(self, tarball_path: Path):
        self.tarball_path = tarball_path
        self.temp_dir = None
    
    def extract(self) -> Path:
        """Extract tarball and return path to extracted directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="goose_check_")
        temp_path = Path(self.temp_dir)
        
        print(f"Extracting {self.tarball_path} to {temp_path}...")
        
        # Determine compression type from extension
        if str(self.tarball_path).endswith('.zstd') or str(self.tarball_path).endswith('.zst'):
            # Use tar with zstd
            subprocess.run(
                ["tar", "--zstd", "-xf", str(self.tarball_path), "-C", str(temp_path)],
                check=True
            )
        else:
            # Use Python's tarfile
            with tarfile.open(self.tarball_path) as tar:
                tar.extractall(path=temp_path)
        
        # Find the actual source directory (usually has the project name)
        extracted_dirs = list(temp_path.iterdir())
        if len(extracted_dirs) == 1 and extracted_dirs[0].is_dir():
            return extracted_dirs[0]
        
        return temp_path
    
    def cleanup(self):
        """Clean up temporary directory."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)


def generate_report(dependencies: Dict[str, str], results: Dict[str, Tuple[bool, str, List[str]]], 
                   output_format: str = "text", dep_type: str = "direct (top-level)",
                   dep_sources: Dict[str, List[str]] = None):
    """Generate a report of the dependency check results."""
    
    found = {name: (ver, msg, pkgs) for name, (ver, (exists, msg, pkgs)) in 
             ((k, (v, results[k])) for k, v in dependencies.items()) if exists}
    missing = {name: (ver, msg, pkgs) for name, (ver, (exists, msg, pkgs)) in 
               ((k, (v, results[k])) for k, v in dependencies.items()) if not exists}
    
    if output_format == "json":
        report = {
            "dependency_type": dep_type,
            "total": len(dependencies),
            "found": len(found),
            "missing": len(missing),
            "found_packages": {},
            "missing_packages": {},
        }
        
        # Add found packages with source info if available
        for name, (ver, msg, pkgs) in found.items():
            entry = {
                "version": ver,
                "message": msg,
                "fedora_packages": pkgs
            }
            if dep_sources and name in dep_sources:
                entry["defined_in"] = dep_sources[name]
            report["found_packages"][name] = entry
        
        # Add missing packages with source info if available
        for name, (ver, msg, pkgs) in missing.items():
            entry = {
                "version": ver,
                "message": msg
            }
            if dep_sources and name in dep_sources:
                entry["defined_in"] = dep_sources[name]
            report["missing_packages"][name] = entry
        
        print(json.dumps(report, indent=2))
    
    else:  # text format
        report_title = "ALL DEPENDENCY" if "total" in dep_type else "TOP-LEVEL DEPENDENCY"
        print("\n" + "="*80)
        print(f"{report_title} CHECK REPORT")
        print("="*80)
        print(f"\nTotal {dep_type} dependencies: {len(dependencies)}")
        print(f"Found in Fedora: {len(found)} ({len(found)/len(dependencies)*100:.1f}%)")
        print(f"Missing from Fedora: {len(missing)} ({len(missing)/len(dependencies)*100:.1f}%)")
        
        if missing:
            print("\n" + "-"*80)
            print("❌ MISSING DEPENDENCIES:")
            print("-"*80)
            for name in sorted(missing.keys()):
                ver, msg, pkgs = missing[name]
                print(f"  {name:40s} v{ver:15s} {msg}")
                # Show where this dependency is defined if we have that info
                if dep_sources and name in dep_sources:
                    sources_str = ", ".join(dep_sources[name])
                    print(f"    └─ defined in: {sources_str}")
        
        if found:
            print("\n" + "-"*80)
            print("✅ FOUND DEPENDENCIES:")
            print("-"*80)
            for name in sorted(found.keys()):
                ver, msg, pkgs = found[name]
                # Show the primary package name
                fedora_pkg = pkgs[0] if pkgs else "unknown"
                print(f"  {name:40s} v{ver:15s} => {fedora_pkg}")
                # Show where this dependency is defined if we have that info
                if dep_sources and name in dep_sources and len(dep_sources[name]) > 1:
                    # Only show sources if it's used in multiple places
                    sources_str = ", ".join(dep_sources[name])
                    print(f"    └─ used in: {sources_str}")
        
        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description="Check if Rust dependencies from goose tarball exist in Fedora",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check dependencies from root Cargo.toml only
  %(prog)s goose-1.13.1-patched.tar.zstd
  
  # Check dependencies from ALL Cargo.toml files (including crates/)
  %(prog)s --all-crates goose-1.13.1-patched.tar.zstd
  
  
  # Preview spec file updates (dry-run)
  %(prog)s --all-crates --update-spec packaging/goose.spec --draft goose.tar.zstd
  
  # Clear the cache
  %(prog)s --clear-cache
  
  # Check from an already extracted directory
  %(prog)s --source-dir ./goose-1.13.1
  
  # Output in JSON format with source tracking
  %(prog)s --all-crates --format json goose-1.13.1-patched.tar.zstd
        """
    )
    
    parser.add_argument(
        "tarball",
        nargs="?",
        type=Path,
        help="Path to goose tarball (e.g., goose-1.13.1-patched.tar.zstd)"
    )
    
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Path to already extracted source directory (skip extraction)"
    )
    
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't clean up temporary extraction directory"
    )
    
    parser.add_argument(
        "--all-deps",
        action="store_true",
        help="Check all dependencies including transitive ones (default: only top-level from Cargo.toml)"
    )
    
    parser.add_argument(
        "--all-crates",
        action="store_true",
        help="Scan all Cargo.toml files in the project (including crates/ subdirectories)"
    )
    
    parser.add_argument(
        "--update-spec",
        type=Path,
        metavar="SPEC_FILE",
        help="Update the spec file with BuildRequires and Provides"
    )
    
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Show what would be changed without modifying files (dry-run)"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the persistent cache and exit"
    )
    
    parser.add_argument(
        "--cache-file",
        type=Path,
        help="Path to cache file (default: ~/.cache/goose-fedora-deps.json)"
    )
    
    args = parser.parse_args()
    
    # Initialize cache manager
    cache_manager = CacheManager(cache_file=args.cache_file if hasattr(args, 'cache_file') and args.cache_file else None)
    
    # Handle --clear-cache
    if args.clear_cache:
        cache_manager.clear()
        print(f"✓ Cache cleared: {cache_manager.cache_file}")
        return 0
    
    # Validate arguments
    if not args.source_dir and not args.tarball:
        parser.error("Either tarball or --source-dir must be provided")
    
    if args.tarball and not args.tarball.exists():
        print(f"Error: Tarball not found: {args.tarball}", file=sys.stderr)
        return 1
    
    if args.source_dir and not args.source_dir.exists():
        print(f"Error: Source directory not found: {args.source_dir}", file=sys.stderr)
        return 1
    
    extractor = None
    source_dir = None
    
    try:
        # Extract tarball or use provided source directory
        if args.source_dir:
            source_dir = args.source_dir
            if not args.quiet:
                print(f"Using source directory: {source_dir}")
        else:
            extractor = TarballExtractor(args.tarball)
            source_dir = extractor.extract()
            if not args.quiet:
                print(f"Extracted to: {source_dir}")
        
        # Parse dependencies
        if not args.quiet:
            print("\nParsing Cargo files...")
        
        cargo_parser = CargoParser(source_dir)
        
        # Determine which dependencies to check
        dep_sources = None
        if args.all_crates:
            # Get dependencies from all Cargo.toml files with source tracking
            deps_with_sources = cargo_parser.get_all_direct_dependencies_with_sources()
            dependencies = {name: version for name, (version, sources) in deps_with_sources.items()}
            dep_sources = {name: sources for name, (version, sources) in deps_with_sources.items()}
            
            if not args.quiet:
                num_cargo_files = len(cargo_parser.find_all_cargo_tomls())
                print(f"Found {num_cargo_files} Cargo.toml files")
            
            dep_type = "direct (from all crates)"
        elif args.all_deps:
            dependencies = cargo_parser.get_all_dependencies()
            dep_type = "total"
        else:
            dependencies = cargo_parser.get_direct_dependencies()
            dep_type = "direct (root only)"
        
        if not dependencies:
            print("Warning: No dependencies found!", file=sys.stderr)
            return 1
        
        if not args.quiet:
            print(f"Found {len(dependencies)} {dep_type} dependencies")
        
        # Check each dependency in Fedora
        if not args.quiet:
            print("\nChecking dependencies in Fedora repositories...")
            cache_info = f" (using cache: {cache_manager.cache_file})"
            print(f"(This may take a while...{cache_info})\n")
        
        checker = FedoraChecker(quiet=args.quiet, cache_manager=cache_manager)
        results = {}
        
        for i, (name, version) in enumerate(sorted(dependencies.items()), 1):
            if not args.quiet:
                print(f"[{i}/{len(dependencies)}] Checking {name:40s} ", end="", flush=True)
            
            exists, message, packages = checker.check_crate(name)
            results[name] = (exists, message, packages)
            
            if not args.quiet:
                if exists and packages:
                    # Show the Fedora package name
                    print(f"✓ {packages[0]}")
                else:
                    status = "✗ MISSING"
                    print(f"{status}")
        
        # Save cache
        if not args.quiet:
            print("\nSaving cache...")
        cache_manager.save()
        
        # Generate report
        generate_report(dependencies, results, args.format, dep_type, dep_sources)
        
        # Update spec file if requested
        if args.update_spec:
            try:
                if not args.quiet:
                    print(f"\n{'Draft mode - ' if args.draft else ''}Updating spec file: {args.update_spec}")
                
                updater = SpecFileUpdater(args.update_spec)
                preview = updater.update_spec(dependencies, results, draft=args.draft)
                print(preview)
                
                if not args.draft:
                    print(f"✓ Spec file updated: {args.update_spec}")
                else:
                    print("ℹ️  Draft mode - no changes made. Remove --draft to apply changes.")
            
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"Error updating spec file: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                return 1
        
        return 0
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        return 130
    
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Cleanup
        if extractor and not args.no_cleanup:
            if not args.quiet:
                print("\nCleaning up temporary files...")
            extractor.cleanup()


if __name__ == "__main__":
    sys.exit(main())

